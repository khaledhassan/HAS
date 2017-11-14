import json
import yaml
from circuits import handler, Component, Event
import paho.mqtt.client as mqtt

mqtt_server = "mqtt" # Handled by docker-compose link, XXX/TODO: make this an environment variable with default to something

config = {} # XXX/TODO: move all config data into this dict so we can access it from all controllers without
            # having to pass it back and forth a lot

nodes = {}

class ac_sensor(Event):
    """AC Sensor Read Event"""

class AcController(Component):
    def __init__(self, mqtt_client):
        super(AcController, self).__init__()
        self.mqtt_client = mqtt_client

    @handler("ac_sensor")
    def handle_msg(self, msg):
        print("AC Controller got msg:")
        print(msg)

class motion_sensor(Event):
    """Motion Detected Event, this event fires all controllers, but only one will respond"""

class LightController(Component):
    def __init__(self, mqtt_client, mac):
        super(LightController, self).__init__()
        self.mqtt_client = mqtt_client
        self.mac = mac
        self.state = False # False means off, True means on. Query the light's actual state next:
        self.query_status()

    def query_status(self):
        msg = json.dumps({"id": self.mac, "cmd": "state"})
        self.mqtt_client.publish("actuator/{}".format(self.mac), msg)

    @handler("motion_sensor")
    def handle_msg(self, msg):
        print("Light Controller got msg:")
        print(msg)
        if "mac" in msg:
            if msg["mac"] == self.mac:
                if "state" in msg:
                    self.state = msg["state"]
                if "motion" in msg:
                    pass # XXX/TODO: set last motion datetime, start timer, turn on light if not on
            else:
                pass # message not for us, hopefully there's another controller out there
        else:
            pass # invalid message?


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

        if not self.sub_controllers_initialized:
            self.sub_controllers_initialized = True
            # register sub-controllers
            self += AcController(self.client)
            for node in nodes:
                if node["type"] == "LIGHT":
                    self += LightController(self.client, node["mac"])


    def mqtt_on_message(self, client, userdata, msg_raw):
        msg = json.loads(msg_raw.payload)

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
    MainController().run()

if __name__ == "__main__":
    # load config YAML
    with open("/config/nodes.yml") as f:
        nodes = yaml.load(f)
    main()

