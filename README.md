# HAS: Home Automation System
Class project for EEL5934 IoT Design; Building Automation System using ESP8266 and Raspberry Pi

## Directory structure
Below is a proposed directory structure for this repository. Because the project should remain relatively simple overall, all components live together in the same repository.

```
├── config
│   └──nodes.yml.example
├── controller
│   └──Dockerfile
│   └──other scripts used to run controller
├── docker
│   └──docker-compose.yml runs controller, mqtt broker, web interface
│   └──any Dockerfiles that define our external dependencies, (i.e. mosquitto) just in case they go away
│   └──perhaps amd64 compatible docker-compose.yml (and alternate Dockerfiles in controller/web directories)
├── esp
│   └──1 folder per node type containing Arduino sketches/code 
├── README.md (this file)
├── test
│   └──past experiments kept for reference (Arduino sketches, etc)
├── web
│   └──Dockerfile
│   └──other scripts/assets used to run web interface
```

## MQTT strategy (proposed)
We are using the mosquitto MQTT broker, exposed as port 1883 on the Raspberry Pi's external network connection and the same port toward the other Docker containers.

ESP8266 nodes identify themselves by their WiFi MAC address, which is mapped using the config/nodes.yml file, used by both the web interface and the controller. 

The nodes publish their sensor data as JSON formatted messages on the topic ```sensor/<MAC>``` so that the controller can subscribe to ```sensor/+``` as a single-level wildcard (or use ```sensor/#``` for multi-level) to catch all the sensors using a single subscription. The controller publishes commands on the topic ```actuator/<target MAC>``` such that each node is subscribed to it's own topic. 

*Is this necessary?:* Nodes shall publish messages to ```nodes``` with their MAC address and "connected" (exact format **TBD**) and shall register a last will and testament message with the broker with their MAC address and "disconnected" (again, format **TBD**) so that the controller is aware of their join/part status. The controller should also periodically (rate **TBD**) "ping" the nodes in case it does not recieve the "connected" message if the controller (re)starts after the node connects to the broker.
