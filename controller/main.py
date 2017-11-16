import json
import yaml
from circuits import handler, Component, Event, Debugger
from circuits.core.timers import Timer
import paho.mqtt.client as mqtt

mqtt_server = "mqtt" # Handled by docker-compose link, XXX/TODO: make this an environment variable with default to something

config = {} # XXX/TODO: move all config data into this dict so we can access it from all controllers without
            # having to pass it back and forth a lot

nodes = {}

target_temp = 60 # XXX/TODO: put this in the config object (via YAML, hopefully)
motion_timeout_seconds = 5*60 # 5 minutes, XXX/TODO: put this in the config object (via YAML, hopefully)

class ac_sensor(Event):
    """AC Sensor Read Event"""

class AcController(Component):
    def __init__(self, mqtt_client, mac):
        super(AcController, self).__init__()
        self.mqtt_client = mqtt_client
        self.mac = mac

    @handler("ac_sensor")
    def handle_msg(self, msg):
        print("AC Controller got msg:")
        print(msg)
        if "t" in msg:
            current_temp = msg["t"]
            # XXX/TODO: maintain state of fan and only send message once and refactor into change_fan_state function
            if current_temp > target_temp:
                msg = json.dumps({"mac": self.mac, "type": "FANON"})
                self.mqtt_client.publish("actuator/{}".format(self.mac), msg)
            elif current_temp <= target_temp:
                msg = json.dumps({"mac": self.mac, "type": "FANOFF"})
                self.mqtt_client.publish("actuator/{}".format(self.mac), msg)


class motion_sensor(Event):
    """Motion Detected Event, this event fires all controllers, but only one will respond"""

class motion_timeout(Event):
    """Motion Sensor Timeout"""

class LightController(Component):
    def __init__(self, mqtt_client, mac):
        super(LightController, self).__init__()
        self.mqtt_client = mqtt_client
        self.mac = mac
        self.timer = None
        self.state = False # False means off, True means on. Query the light's actual state next:
        self.query_state()

    def query_state(self):
        msg = json.dumps({"mac": self.mac, "cmd": "state"})
        self.mqtt_client.publish("actuator/{}".format(self.mac), msg, retain=True) # retained message in case the controller starts before the node connects

    def change_state(self, want_on):
        if want_on:
            msg = json.dumps({"mac": self.mac, "cmd": "light_on"})
        else:
            msg = json.dumps({"mac": self.mac, "cmd": "light_off"})

        self.mqtt_client.publish("actuator/{}".format(self.mac), msg)
        self.state = want_on

    @handler("motion_sensor")
    def handle_msg(self, msg):
        if "mac" in msg:
            if msg["mac"] == self.mac:
                if "state" in msg:
                    self.state = msg["state"]
                if "motion" in msg:
                    self.change_state(want_on = True)

                    if self.timer is not None: # set to None in __init__ and the handler for "motion_timeout"
                        self.timer.reset() # if there was a timer from last time, reset it
                    else:
                        self.timer = Timer(motion_timeout_seconds, motion_timeout(self.mac))
                        self += self.timer # otherwise, re-register it (why does "self.register(self.timer)" not work?)
            else:
                pass # message not for us, hopefully there's another controller out there
        else:
            pass # invalid message?

    @handler("motion_timeout")
    def handle_timer(self, mac):
        if mac == self.mac:
            self.change_state(want_on = False)
            self.timer = None # get ready for next motion detected
        else:
            pass # not meant for us!

class MainController(Component):
    def __init__(self):
        super(MainController, self).__init__()
        self.client = mqtt.Client()
        self.client.on_connect = self.mqtt_on_connect
        self.client.on_message = self.mqtt_on_message
        self.sub_controllers_initialized = False


    def started(self, *args):
        self.client.connect(mqtt_server, 1883, 60)
        self.client.loop_start()

    def mqtt_on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.client.subscribe("sensor/#")
        self.client.subscribe("join_leave/#")
        self.client.subscribe("target_temp")

        if not self.sub_controllers_initialized:
            self.sub_controllers_initialized = True
            # register sub-controllers
            for node in nodes:
                if node["type"] == "AC":
                    self += AcController(self.client, node["mac"])
                if node["type"] == "LIGHT":
                    self += LightController(self.client, node["mac"])


    def mqtt_on_message(self, client, userdata, msg_raw):
        msg = json.loads(msg_raw.payload)

        if msg_raw.topic == "target_temp":
            global target_temp
            target_temp = int(msg_raw.payload)

        if msg_raw.topic.startswith("sensor"):
            if "mac" in msg:
                for node in nodes:
                    if node["mac"] == msg["mac"]:
                        if node["type"] == "AC":
                            self.fire(ac_sensor(msg))
                        elif node["type"] == "LIGHT":
                            self.fire(motion_sensor(msg))
                        elif node["type"] == "LOCK":
                            pass
            else:
                pass # invalid message, doesn't have "mac" field
        if msg_raw.topic.startswith("join_leave"):
            if ("mac" in msg) and ("status" in msg):
                for node in nodes:
                    if node["mac"] == msg["mac"]:
                        if msg["status"] == "join":
                            node["online"] = True
                        elif msg["status"] == "leave":
                            node["online"] = False
                        else:
                            pass # invalid message (status unknown)
            else:
                pass # invalid message (needs mac and status)

# end MainController

def main():
    (MainController() + Debugger()).run()

if __name__ == "__main__":
    # load config YAML
    with open("/config/nodes.yml") as f:
        nodes = yaml.load(f)
    main()

