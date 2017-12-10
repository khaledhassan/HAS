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
    mqtt_server = "mqtt"  # Handled by docker-compose link

config = {}  # XXX/TODO: move all config data into this dict so we can access it from all controllers without
             # having to pass it back and forth a lot

nodes = {}

motion_timeout_seconds = 5*60  # 5 minutes, XXX/TODO: put this in the config object (via YAML, hopefully)


class ac_sensor(Event):
    """AC Sensor Read Event"""


class ac_control(Event):
    """AC control message via WebSockets"""


class AcController(Component):
    def __init__(self, mqtt_client, ws_client, mac):
        super(AcController, self).__init__()
        self.mqtt_client = mqtt_client
        self.ws_client = ws_client
        self.fan_on = False
        self.mac = mac
        self.auto_mode = False
        self.target_temp = 70

    def change_state(self, want_on):
        #XXX/TODO: now that we've refactored into a function that uses fan state, implement a state query command like we have in the light controller
        if want_on is not self.fan_on:
            msg = json.dumps({"mac": self.mac, "type": "ac", "action": "on" if want_on else "off"})
            self.mqtt_client.publish("actuator/{}".format(self.mac), msg)
            self.fan_on = want_on

    @handler("ac_sensor")
    def handle_mqtt_msg(self, msg):
        if self.auto_mode and "t" in msg:
            current_temp = msg["t"]
            if current_temp > self.target_temp:
                self.change_state(True)
            elif current_temp <= self.target_temp:
                self.change_state(False)

        ws_payload = {"type": "ac", "status": "on" if self.fan_on else "off"}
        if "t" in msg:
            ws_payload["t"] = msg["t"]
        if "h" in msg:
            ws_payload["h"] = msg["h"]
        self.ws_client.send(json.dumps(ws_payload))

    @handler("ac_control")
    def handle_ws_msg(self, msg):
        if "mode" in msg:
            self.auto_mode = True if msg["mode"] == "auto" else False
            # set auto_mode before reading action so it makes
            # sense if mode and target temp are set at the same time
        if "action" in msg:
            try:  # I would prefer to check self.auto_mode, but the message received may be inconsistent
                self.target_temp = int(msg["action"])
            except ValueError:  # not an integer
                if msg["action"] == "on":
                    self.change_state(True)
                if msg["action"] == "off":
                    self.change_state(False)


class light_sensor(Event):
    """Motion Detected Event, this event fires all controllers, but only one will respond"""


class light_control(Event):
    """Light control message via WebSockets"""


class light_timeout(Event):
    """Motion Sensor Timeout"""


class LightController(Component):
    def __init__(self, mqtt_client, ws_client, mac):
        super(LightController, self).__init__()
        self.mqtt_client = mqtt_client
        self.ws_client = ws_client
        self.mac = mac
        self.auto_mode = False
        self.timer = None
        self.state = False  # False means off, True means on. Query the light's actual state next:
        self.query_state()

    def query_state(self):
        msg = json.dumps({"mac": self.mac, "type": "light", "action": "status"})
        self.mqtt_client.publish("actuator/{}".format(self.mac), msg, retain=True)
        # retained message in case the controller starts before the node connects

    def change_state(self, want_on):
        self.state = want_on
        mqtt_payload = json.dumps({"mac": self.mac, "type": "light", "action": "on" if self.state else "off"})
        self.mqtt_client.publish("actuator/{}".format(self.mac), mqtt_payload)
        ws_payload = json.dumps({"type": "light", "status": "on" if self.state else "off"})
        self.ws_client.send(ws_payload)

    @handler("light_sensor")
    def handle_mqtt_msg(self, msg):
        if "mac" in msg:
            if msg["mac"] == self.mac:
                if "state" in msg:
                    self.state = msg["state"]
                if self.auto_mode and "motion" in msg:
                    self.change_state(True)
                    if self.timer is not None:  # set to None in __init__ and the handler for "light_timeout"
                        self.timer.reset()  # if there was a timer from last time, reset it
                    else:
                        self.timer = Timer(motion_timeout_seconds, light_timeout(self.mac))
                        self += self.timer  # otherwise, re-register it (why does "self.register(self.timer)" not work?)
            else:
                pass  # message not for us, hopefully there's another controller out there

    @handler("light_control")
    def handle_ws_msg(self, msg):
        if "mode" in msg:
            self.auto_mode = True if msg["mode"] == "auto" else False
        if "action" in msg:
            if msg["action"] == "on":
                self.change_state(True)
            if msg["action"] == "off":
                self.change_state(False)

    @handler("light_timeout")
    def handle_timer(self, mac):
        if mac == self.mac:
            if self.auto_mode:
                self.change_state(False)
            self.timer = None  # get ready for next motion detected
        else:
            pass  # not meant for us!


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

    @handler("door_sensor")
    def handle_mqtt_msg(self, msg):
        if "mac" in msg:
            if msg["mac"] == self.mac:
                if "locked" in msg:
                    ws_payload = json.dumps({"type": "door", "status": "locked" if msg["status"] == "locked" else "unlocked"})
                    self.ws_client.send(ws_payload)

    @handler("door_control")
    def handle_ws_msg(self, msg):
        if "action" in msg:
            mqtt_payload = json.dumps({"mac": self.mac, "type": "door", "action": "unlock" if msg["action"] == "unlock" else "lock"})
            self.mqtt_client.publish("actuator/{}".format(self.mac), mqtt_payload)


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
        self.wsthread = WSThread("ws://web:8080",  # TODO/FIXME/XXX: set this via an env variable
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
                    self += AcController(self.mqtt_client, self.ws_client, node["mac"])
                if node["type"] == "LIGHT":
                    self += LightController(self.mqtt_client, self.ws_client, node["mac"])
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
                            self.fire(light_sensor(msg))
                        elif node["type"] == "DOOR":
                            self.fire(door_sensor(msg))
            else:
                pass  # invalid message, doesn't have "mac" field
        if msg_raw.topic.startswith("join_leave"):
            if ("mac" in msg) and ("status" in msg):
                for node in nodes:
                    if node["mac"] == msg["mac"]:
                        if msg["status"] == "join":
                            node["online"] = True
                        elif msg["status"] == "leave":
                            node["online"] = False
                        else:
                            pass  # invalid message (status unknown)
            else:
                pass  # invalid message (needs mac and status)

    def ws_on_open(self, ws):
        print("WebSocket connected")

    def ws_on_message(self, ws, message):
        try:
            msg = json.loads(message)
            if "type" in msg:
                if msg["type"] == "ac":
                    self.fire(ac_control(msg))
                elif msg["type"] == "light":
                    self.fire(light_control(msg))
                elif msg["type"] == "door":
                    self.fire(door_control(msg))
        except ValueError:
            pass  # invalid JSON

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

