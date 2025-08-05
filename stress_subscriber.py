import asyncio
import json
import statistics
import time

import paho.mqtt.client as mqtt
from tqdm.asyncio import tqdm as async_tqdm  # Optional for async progress bar

# --- Configuration ---
BROKER_ADDRESS = "localhost"  # Connect to the exposed port of emqx1 (or HAProxy)
BROKER_PORT = 1884
NUM_SUBSCRIBERS = 100  # Number of simulated subscriber clients
SUBSCRIBE_TOPIC = "sensors/data/#"  # Subscribe to all sensor data
QOS = 2  # QoS level for subscription (0, 1, or 2)
EXPECTED_TOTAL_MESSAGES = 100 * 10  # Example: if publisher has 20 clients * 10 messages each

# --- Global Variables for Metrics ---
received_messages_count = 0
latency_measurements = []
message_sequence = {}  # Track last message number per client for potential drops
active_clients = []  # Global list to keep track of clients for clean shutdown

# --- Flag for graceful shutdown ---
shutdown_event = asyncio.Event()


def on_message(client, userdata, msg):
    global received_messages_count
    global latency_measurements
    global message_sequence

    received_messages_count += 1

    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        publisher_timestamp = payload.get("timestamp")

        print(f"Received payload: {payload}")

        if publisher_timestamp:
            latency = time.time() - publisher_timestamp
            latency_measurements.append(latency)

        msg_publisher_id = payload.get("client_id")  # Use a different var name for clarity
        msg_num = payload.get("msg_num")

        if msg_publisher_id not in message_sequence:
            message_sequence[msg_publisher_id] = msg_num
        elif msg_num != message_sequence[msg_publisher_id] + 1:
            pass
        message_sequence[msg_publisher_id] = msg_num

    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON payload: {msg.payload.decode()}")
    except Exception as e:
        print(f"Error processing message: {e}")


def on_disconnect(client, userdata, flags, rc, properties):
    if rc != 0:
        print(f"Subscriber {client._client_id} unexpectedly disconnected (RC: {rc}).")


async def create_mqtt_subscriber_client(client_id):
    """Creates and connects an MQTT subscriber client."""
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                         protocol=mqtt.MQTTv311)  # Or mqtt.MQTTv5
    client.connected_flag = False

    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            client.connected_flag = True
            print(f"Subscriber {client_id} connected successfully.")
            client.subscribe(SUBSCRIBE_TOPIC, qos=QOS)
            print(f"Subscriber {client_id} subscribed to topic: {SUBSCRIBE_TOPIC}")
        else:
            print(f"Subscriber {client_id} failed to connect, return code {rc}")
            client.connected_flag = False

    client.on_connect = on_connect
    client.on_message = on_message  # Now assigned to the global on_message
    client.on_disconnect = on_disconnect  # Now assigned to the global on_disconnect

    try:
        client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=60)
        client.loop_start()

        while not client.connected_flag and not shutdown_event.is_set():
            await asyncio.sleep(0.1)

        if client.connected_flag:
            active_clients.append(client)
            return client
        else:
            client.loop_stop()
            client.disconnect()
            return None
    except Exception as e:
        print(f"Error connecting subscriber client {client_id}: {e}")
        return None


async def subscriber_monitor_task():
    """Monitors the received messages and prints progress."""
    global received_messages_count

    print(f"Awaiting {EXPECTED_TOTAL_MESSAGES} messages...")

    with async_tqdm(total=EXPECTED_TOTAL_MESSAGES, desc="Receiving Progress") as pbar:
        last_count = 0
        while received_messages_count < EXPECTED_TOTAL_MESSAGES and not shutdown_event.is_set():
            await asyncio.sleep(0.5)
            current_count = received_messages_count
            if current_count > last_count:
                pbar.update(current_count - last_count)
                last_count = current_count

            pbar.total = max(pbar.total, received_messages_count)

            if received_messages_count >= EXPECTED_TOTAL_MESSAGES:
                break

    if received_messages_count >= EXPECTED_TOTAL_MESSAGES:
        print("All expected messages received.")
    elif shutdown_event.is_set():
        print("Subscriber monitoring stopped due to shutdown signal.")
    else:
        print("Subscriber monitoring ended (timeout or unexpected condition).")


async def main():
    global received_messages_count, latency_measurements

    subscriber_creation_tasks = []
    for i in range(NUM_SUBSCRIBERS):
        client_id = f"subscriber-{i:02d}"
        subscriber_creation_tasks.append(create_mqtt_subscriber_client(client_id))

    connected_clients = await asyncio.gather(*subscriber_creation_tasks)
    clients = [c for c in connected_clients if c is not None]

    if not clients:
        print("No subscriber clients connected. Exiting.")
        return

    start_time = time.time()  # This should be where the actual test start time is recorded

    monitor_task = asyncio.create_task(subscriber_monitor_task())

    try:
        await monitor_task
    except asyncio.CancelledError:
        print("Subscriber main loop cancelled (e.g., due to KeyboardInterrupt).")
    except Exception as e:
        print(f"An error occurred during subscriber main loop: {e}")
        shutdown_event.set()

    end_time = time.time()
    total_duration = end_time - start_time

    print("\n--- Test Results (Subscriber) ---")
    print(f"Total simulated subscribers: {NUM_SUBSCRIBERS}")
    print(f"Total messages received: {received_messages_count}")
    print(f"Test duration: {total_duration:.2f} seconds")

    if total_duration > 0 and received_messages_count > 0:
        print(f"Average receive rate: {received_messages_count / total_duration:.2f} messages/second")
    elif received_messages_count == 0:
        print("No messages received.")
    else:
        print("Test duration was zero or no messages received.")

    if latency_measurements:
        print("Latency (seconds):")
        print(f"  Min: {min(latency_measurements):.4f}")
        print(f"  Max: {max(latency_measurements):.4f}")
        print(f"  Avg: {statistics.mean(latency_measurements):.4f}")
        print(f"  Median: {statistics.median(latency_measurements):.4f}")
        if len(latency_measurements) >= 100:
            print(f"  90th Percentile: {statistics.quantiles(latency_measurements, n=10)[8]:.4f}")
            print(f"  99th Percentile: {statistics.quantiles(latency_measurements, n=100)[98]:.4f}")

    # Final cleanup for clients
    for active_client in active_clients[:]:
        if active_client:
            print(f"Finalizing disconnect for client {active_client._client_id}...")
            active_client.loop_stop()
            active_client.disconnect()
            if active_client in active_clients:
                active_clients.remove(active_client)

    print("Subscriber script finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Initiating graceful shutdown...")

        shutdown_event.set()

        asyncio.run(asyncio.sleep(0.5))

        print("Performing final MQTT client cleanup...")
        for active_client in active_clients[:]:
            if active_client:
                print(f"Disconnecting client {active_client._client_id}...")
                active_client.loop_stop()
                active_client.disconnect()
                if active_client in active_clients:
                    active_clients.remove(active_client)
        print("All clients disconnected. Exiting.")
    except Exception as e:
        import traceback

        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
    finally:
        for active_client in active_clients[:]:
            if active_client:
                active_client.loop_stop()
                active_client.disconnect()
                if active_client in active_clients:
                    active_clients.remove(active_client)
