import json
import yaml
from circuits import handler, Component, Event
import paho.mqtt.client as mqtt

online_list = {}
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
    def __init__(self, mac):
        super(LightController, self).__init__()
        self.mac = mac

    @handler("motion_sensor")
    def handle_msg(self, msg):
        print("Light Controller got msg:")
        print(msg)

class MainController(Component):
    def __init__(self):
        super(MainController, self).__init__()
        self.client = mqtt.Client()
        self.client.on_connect = self.mqtt_on_connect
        self.client.on_message = self.mqtt_on_message
        # register sub-controllers
        self += AcController(self.client)
        for node in nodes:
            if node["type"] == "LIGHT":
                self += LightController(node["mac"])

    def started(self, *args):
        self.client.connect(mqtt_server, 1883, 60)
        self.client.loop_start()

    def mqtt_on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.client.subscribe("sensor/#")
        self.client.subscribe("join_leave")

    def mqtt_on_message(self, client, userdata, msg_raw):
        msg = json.loads(msg_raw.payload)

        if msg_raw.topic.startswith("sensor"):
            for node in nodes:
                if node["mac"] == msg["mac"]:
                    if node["type"] == "AC":
                        self.fire(ac_sensor(msg))
                    elif node["type"] == "LIGHT":
                        self.fire(motion_sensor(msg))
                    elif node["type"] == "LOCK":
                        pass

# end MainController

def main():
    MainController().run()

if __name__ == "__main__":
    # load config YAML
    with open("/config/nodes.yml") as f:
        nodes = yaml.load(f)
    main()

