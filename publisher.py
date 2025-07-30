import time

import paho.mqtt.client as mqtt

broker_address = "localhost"
port = 1883
topic = "python/test/topic"


def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")


client = mqtt.Client()
client.on_connect = on_connect

client.connect(broker_address, port, 60)
client.loop_start()  # Start a non-blocking loop for network traffic

try:
    for i in range(5):
        message = f"Hello from Python! Message #{i + 1}"
        client.publish(topic, message, qos=1)
        print(f"Published: {message}")
        time.sleep(2)  # Wait 2 seconds before publishing next message

except KeyboardInterrupt:
    print("Publisher stopped.")

client.loop_stop()
client.disconnect()
