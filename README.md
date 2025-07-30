# Start MQTT broker
```docker pull emqx/emqx:latest```

```docker run -d --rm --name emqx -p 1883:1883 -p 8083:8083 -p 8084:8084 -p 8883:8883 -p 18083:18083 -e EMQX_DASHBOARD__DEFAULT_USERNAME=admin EMQX_DASHBOARD__DEFAULT_PASSWORD=admin_123 emqx/emqx:latest```
 - access it on http://localhost:18083 using admin,public as credentials

# Option 1: On NodeJS
```npm install -g mqttx-cli```

then:

```mqttx sub -h localhost -p 1883 -t "test/topic"```

then on a second tab:

```mqttx pub -h localhost -p 1883 -t "test/topic" -m "Hello, EMQX! This is my first MQTT message."```


# Option 2: On Python
first start by installing the module ```pip install paho-mqtt```

## Simple Single-node Test
execute these on separate tabs:

```
python simple_subscriber.py
python simple_publisher.py
```

## Cluster Multi-node Stress Test

To have a cluster of nodes for EMQX we need to have a valid license for enterprise application development from EMQX. You can get
a 15-day trial license, but for production, you need to purchase one. Without the license, you can only have a single-node community
version of EMQX to play with. Add your license to ```emqx.conf``` file.

We have an HAProxy server act as a load balancer on top of EMQX cluster to distribute load on the two existing nodes.

To start the test, first start the docker compose:

```docker compose -f .\docker-compose.yaml up -d```

Then, start subscriber and publisher as below on separate tabs:

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

# Scalability Test
docker network create emqx-cluster-net

docker run -d --name emqx1 --network emqx-cluster-net -p 1883:1883 -p 8083:8083 -p 18083:18083 -e EMQX_NODE__DIST_LISTEN_MAX=256 emqx/emqx:latest

docker run -d --name emqx2 --network emqx-cluster-net -e EMQX_NODE__DIST_LISTEN_MAX=256 emqx/emqx:latest

docker run -d --name emqx3 --network emqx-cluster-net -e EMQX_NODE__DIST_LISTEN_MAX=256 emqx/emqx:latest


docker inspect -f "Container: {{.Name}}, IP: {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" emqx1 emqx2 emqx3

docker stop emqx1 emqx2 emqx3
docker rm emqx1 emqx2 emqx3


docker run -d --name emqx1 --network emqx-cluster-net -p 1883:1883 -p 8083:8083 -p 18083:18083 -e EMQX_NODE__DIST_LISTEN_MAX=256 -e EMQX_CLUSTER__DISCOVERY_STRATEGY=static -e EMQX_CLUSTER__STATIC__SEEDS="emqx1@172.19.0.2,emqx2@172.19.0.3,emqx3@172.19.0.4" emqx/emqx:latest

docker run -d --name emqx2 --network emqx-cluster-net -e EMQX_NODE__DIST_LISTEN_MAX=256 -e EMQX_CLUSTER__DISCOVERY_STRATEGY=static -e EMQX_CLUSTER__STATIC__SEEDS="emqx1@172.19.0.2,emqx2@172.19.0.3,emqx3@172.19.0.4" emqx/emqx:latest

docker run -d --name emqx3 --network emqx-cluster-net -e EMQX_NODE__DIST_LISTEN_MAX=256 -e EMQX_CLUSTER__DISCOVERY_STRATEGY=static -e EMQX_CLUSTER__STATIC__SEEDS="emqx1@172.19.0.2,emqx2@172.19.0.3,emqx3@172.19.0.4" emqx/emqx:latest
