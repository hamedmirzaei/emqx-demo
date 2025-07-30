# Simple Single-node Test

# Option 1: On Python
Start MQTT broker

```
docker pull emqx/emqx:latest
docker run -d --rm --name emqx -p 1883:1883 -p 8083:8083 -p 8084:8084 -p 8883:8883 -p 18083:18083 -e EMQX_DASHBOARD__DEFAULT_USERNAME=admin EMQX_DASHBOARD__DEFAULT_PASSWORD=admin_123 emqx/emqx:latest
```
access the EMQX dashboard on ```http://localhost:18083``` using admin,public as credentials

then, install the python module:

```pip install paho-mqtt```

finally, execute these on separate tabs:

```
python simple_subscriber.py
python simple_publisher.py
```

## Option 2: On NodeJS
Start MQTT broker

```
docker pull emqx/emqx:latest
docker run -d --rm --name emqx -p 1883:1883 -p 8083:8083 -p 8084:8084 -p 8883:8883 -p 18083:18083 -e EMQX_DASHBOARD__DEFAULT_USERNAME=admin EMQX_DASHBOARD__DEFAULT_PASSWORD=admin_123 emqx/emqx:latest
```
access the EMQX dashboard on ```http://localhost:18083``` using admin,public as credentials

then, install the npm dependency:

```npm install -g mqttx-cli```

then, start a subscriber listening on a test topic:

```mqttx sub -h localhost -p 1883 -t "test/topic"```

finally, on a second tab, start a publisher to publish one message to the same test topic:

```mqttx pub -h localhost -p 1883 -t "test/topic" -m "Hello, EMQX! This is my first MQTT message."```


# Cluster Multi-node Stress Test on Python

To have a cluster of nodes for EMQX we need to have a valid license for enterprise application development from EMQX. You can get
a 15-day trial license, but for production, you need to purchase one. Without the license, you can only have a single-node community
version of EMQX to play with. Add your license to ```emqx.conf``` file.

We have an HAProxy server act as a load balancer on top of EMQX cluster to distribute load on the two existing nodes.

To start the test, first start the docker compose:

```docker compose -f .\docker-compose.yaml up -d```

Then, start subscribers and publishers as below on separate tabs:

```
python stress_subscriber.py
python stress_publisher.py
```

# General Considerations

## Quality of Service (QoS):

Concept: Determines the guarantee of message delivery.

QoS 0 (At most once): "Fire and forget." Fast, low overhead, but messages can be lost. Good for sensor readings where occasional loss is acceptable.

QoS 1 (At least once): Message is guaranteed to arrive, but duplicates are possible. Requires acknowledgment from the broker.

QoS 2 (Exactly once): Message arrives exactly once. Highest overhead, but highest reliability. Good for critical commands (e.g., turning off a machine).

### On NodeJS
```mqttx pub -h localhost -p 1883 -t "test/critical_command" -m "Emergency Shutdown" -q 2```

### On Python
```client.publish(topic, message, qos=1) # or qos=2```


## Retain Messages

Concept: The broker stores the last message published on a topic with the retain flag set to true. When a new subscriber subscribes to that topic, it immediately receives this retained message.

How to add: Set the retain flag to true (or 1).

Why use it: Useful for state information. For instance, if a light's state is "on" or "off", a new subscriber immediately knows the current state without waiting for the next update.

### on NodeJS

```mqttx pub -h localhost -p 1883 -t "home/livingroom/light/status" -m "ON" -r```
(Then, in a new subscriber, subscribe to home/livingroom/light/status and you'll immediately get "ON").

### On Python
```client.publish(topic, message, retain=True)```