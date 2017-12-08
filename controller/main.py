import json
import threading
import os
import yaml
from circuits import handler, Component, Event, Debugger
from circuits.core.timers import Timer
import paho.mqtt.client as mqtt
import websocket

if "MQTT_SERVER" in os.environ:
    mqtt_server = os.environ.get("MQTT_SERVER")
else:
    mqtt_server = "mqtt" # Handled by docker-compose link

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
        self.fan_on = False
        self.mac = mac

    def change_fan_state(self, want_on):
        #XXX/TODO: now that we've refactored into a function that uses fan state, implement a state query command like we have in the light controller
        if want_on is not self.fan_on:
            if want_on:
                msg = json.dumps({"mac": self.mac, "type": "FANON"})
            else:
                msg = json.dumps({"mac": self.mac, "type": "FANOFF"})

            self.mqtt_client.publish("actuator/{}".format(self.mac), msg)
            self.fan_on = want_on


    @handler("ac_sensor")
    def handle_msg(self, msg):
        print("AC Controller got msg:")
        print(msg)
        if "t" in msg:
            current_temp = msg["t"]
            if current_temp > target_temp:
                self.change_fan_state(True)
            elif current_temp <= target_temp:
                self.change_fan_state(False)


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


class door_sensor(Event):
    """Door Sensor message via MQTT"""

class door_control(Event):
    """Door control message via WebSockets"""


class DoorController(Component):
    def __init__(self, mqtt_client, ws_client, mac):
        super(DoorController, self).__init__()
        self.mqtt_client = mqtt_client
        self.ws_client = ws_client
        self.mac = mac

    def started(self, *args):
        pass

    @handler("door_sensor")
    def handle_mqtt_msg(self, msg):
        if "mac" in msg:
            if msg["mac"] == self.mac:
                if "locked" in msg:
                    ws_payload = {"type": "door", "status": ("locked" if msg["locked"] == 1 else "unlocked")}
                    ws_payload_json = json.dumps(ws_payload)
                    self.ws_client.send(ws_payload_json)

    @handler("door_control")
    def handle_ws_msg(self, msg):
        print("in door_control event")
        if "target" in msg:
            mqtt_payload = {"mac": self.mac, "type": ("UNLOCK" if msg["target"] == "on" else "LOCK")}
            mqtt_payload_json = json.dumps(mqtt_payload)
            self.mqtt_client.publish("actuator/{}".format(self.mac), mqtt_payload_json)


class WSThread(threading.Thread):
    def __init__(self, url, on_open, on_message, on_close, on_error):
        threading.Thread.__init__(self)
        self.ws_client = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message,
                                                on_close=on_close, on_error=on_error, keep_running=True)

    def run(self):
        self.ws_client.run_forever()


class MainController(Component):
    def __init__(self):
        super(MainController, self).__init__()
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.mqtt_on_connect
        self.mqtt_client.on_message = self.mqtt_on_message
        self.sub_controllers_initialized = False
        self.wsthread = WSThread("ws://10.42.0.167:8080",  # TODO/FIXME/XXX: set this via an env variable
                                 self.ws_on_open, self.ws_on_message,
                                 self.ws_on_close, self.ws_on_error)
        self.ws_client = self.wsthread.ws_client

    def started(self, *args):
        self.mqtt_client.connect(mqtt_server, 1883, 60)
        self.mqtt_client.loop_start()
        self.wsthread.start()

    def mqtt_on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.mqtt_client.subscribe("sensor/#")
        self.mqtt_client.subscribe("join_leave/#")
        self.mqtt_client.subscribe("target_temp")

        if not self.sub_controllers_initialized:
            self.sub_controllers_initialized = True
            # register sub-controllers
            for node in nodes:
                if node["type"] == "AC":
                    self += AcController(self.mqtt_client, node["mac"])
                if node["type"] == "LIGHT":
                    self += LightController(self.mqtt_client, node["mac"])
                if node["type"] == "DOOR":
                    self += DoorController(self.mqtt_client, self.ws_client, node["mac"])

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
                        elif node["type"] == "DOOR":
                            self.fire(door_sensor(msg))
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

    def ws_on_open(self, ws):
        print("WebSocket connected")

    def ws_on_message(self, ws, message):
        try:
            msg = json.loads(message)
            if "type" in msg:
                if msg["type"] == "door":
                    print("firing door_control event")
                    self.fire(door_control(msg))
        except:
            pass

    def ws_on_close(self, ws):
        print("WebSocket disconnected")

    def ws_on_error(self, ws, error):
        pass


# end MainController


def main():
    (MainController() + Debugger()).run()


if __name__ == "__main__":
    # load config YAML
    if "NODE_CONFIG" in os.environ:
        config_path = os.environ.get("NODE_CONFIG")
    else:
        config_path = "/config/nodes.yml"

    with open(config_path) as f:
        nodes = yaml.load(f)
    main()

