import paho.mqtt.client as mqtt

broker_address = "localhost"
port = 1883
topic = "python/test/topic"


def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(topic)
    print(f"Subscribed to topic: {topic}")


def on_message(client, userdata, msg):
    print(f"Received message on topic '{msg.topic}': {msg.payload.decode()}")


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker_address, port, 60)

# Loop forever to process incoming messages and handle reconnections.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
