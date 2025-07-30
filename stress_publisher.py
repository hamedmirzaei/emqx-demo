import asyncio
import json
import time

import paho.mqtt.client as mqtt
from tqdm.asyncio import tqdm as async_tqdm  # For progress bar

# --- Configuration ---
BROKER_ADDRESS = "localhost"  # Connect to the exposed port of emqx1 (or HAProxy)
BROKER_PORT = 1884
NUM_CLIENTS = 20  # Number of simulated publisher clients
MESSAGES_PER_CLIENT = 10  # How many messages each client sends
MESSAGE_INTERVAL_SEC = 0.1  # Time between messages from a single client
PAYLOAD_SIZE_BYTES = 100  # Size of the message payload (approx)
QOS = 2  # QoS level for published messages (0, 1, or 2)
TOPIC_PREFIX = "sensors/data/"  # Base topic for messages

# --- Global Variables for Metrics ---
published_messages_count = 0
start_time = None
active_clients = []  # Global list to keep track of clients for clean shutdown

# --- Flag for graceful shutdown ---
shutdown_event = asyncio.Event()


def on_disconnect(client, userdata, flags, rc, properties):
    if rc != 0:
        print(f"Publisher {client._client_id} unexpectedly disconnected (RC: {rc}).")


async def create_mqtt_client(client_id):
    """Creates and connects an MQTT client."""
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                         protocol=mqtt.MQTTv311)  # Or mqtt.MQTTv5
    client.connected_flag = False

    def on_connect(client, userdata, flags, rc, properties):
        if rc == 0:
            client.connected_flag = True
        else:
            print(f"Client {client_id} failed to connect, return code {rc}")
            client.connected_flag = False

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(BROKER_ADDRESS, BROKER_PORT, keepalive=60)
        client.loop_start()  # Start background thread to handle network traffic

        # Wait for connection to establish or shutdown event
        while not client.connected_flag and not shutdown_event.is_set():
            await asyncio.sleep(0.1)  # Yield control to other tasks

        if client.connected_flag:
            active_clients.append(client)
            return client
        else:
            # If shutdown was initiated before connection, clean up
            client.loop_stop()
            client.disconnect()
            return None
    except Exception as e:
        print(f"Error connecting client {client_id}: {e}")
        return None


async def publisher_task(client_id):
    """Simulates a single MQTT client publishing messages."""
    global published_messages_count

    client = await create_mqtt_client(client_id)
    if not client:
        return

    topic = f"{TOPIC_PREFIX}{client_id}"
    payload_data = "a" * (PAYLOAD_SIZE_BYTES - len(str(time.time())) - 20)  # Reserve space for timestamp and ID

    try:
        for i in range(MESSAGES_PER_CLIENT):
            if shutdown_event.is_set():  # Check for shutdown signal
                print(f"Publisher {client._client_id} stopping due to shutdown signal.")
                break

            if not client.is_connected():
                print(f"Publisher {client._client_id} lost connection, attempting to reconnect...")
                await asyncio.sleep(1)  # Small delay before checking again
                if not client.is_connected():
                    print(f"Publisher {client._client_id} failed to reconnect, stopping.")
                    break  # Break if cannot reconnect

            timestamp = time.time()
            message_payload = json.dumps({
                "client_id": client_id,
                "msg_num": i + 1,
                "timestamp": timestamp,
                "data": payload_data
            })

            client.publish(topic, message_payload, qos=QOS)
            print(f"Payload published: {message_payload}")
            published_messages_count += 1
            await asyncio.sleep(MESSAGE_INTERVAL_SEC)

    except asyncio.CancelledError:
        print(f"Publisher {client._client_id} task cancelled.")
    except Exception as e:
        print(f"Error publishing for client {client._client_id}: {e}")
    finally:
        # Ensure client cleanup happens if task completes or is cancelled
        if client in active_clients:
            active_clients.remove(client)
        if client:
            print(f"Publisher {client._client_id} disconnecting.")
            client.loop_stop()
            client.disconnect()


async def main():
    global start_time

    start_time = time.time()

    print(f"Starting EMQX scalability test for {NUM_CLIENTS} publishers...")
    print(f"Each client sending {MESSAGES_PER_CLIENT} messages with {PAYLOAD_SIZE_BYTES} bytes payload at QoS {QOS}.")

    tasks = []
    for i in range(NUM_CLIENTS):
        client_id = f"publisher-{i:05d}"
        tasks.append(publisher_task(client_id))

    try:
        # Run all publisher tasks concurrently with a progress bar
        # This will wait for all tasks to complete or be cancelled (e.g., by KeyboardInterrupt)
        await async_tqdm.gather(*tasks, desc="Publishing Progress")
    except asyncio.CancelledError:
        print("Main publishing tasks cancelled.")
    except Exception as e:  # Catch any other unexpected exceptions here
        print(f"An error occurred during publisher main loop: {e}")
        shutdown_event.set()  # Trigger shutdown for other tasks if an error occurs

    end_time = time.time()
    total_duration = end_time - start_time
    total_messages = NUM_CLIENTS * MESSAGES_PER_CLIENT

    print("\n--- Test Results (Publisher) ---")
    print(f"Total simulated clients: {NUM_CLIENTS}")
    print(f"Total messages published: {published_messages_count}/{total_messages}")
    print(f"Test duration: {total_duration:.2f} seconds")
    if total_duration > 0:
        print(f"Average publish rate: {published_messages_count / total_duration:.2f} messages/second")
    else:
        print("Test duration was zero, cannot calculate rate.")

    # Final cleanup for clients that might not have been removed yet (e.g., if script exits naturally)
    for active_client in active_clients[:]:
        if active_client:
            print(f"Finalizing disconnect for client {active_client._client_id} (natural exit)...")
            active_client.loop_stop()
            active_client.disconnect()
            active_clients.remove(active_client)

    print("Publisher script finished.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # This is where Ctrl+C on Windows will be caught.
        # Now we manually trigger the shutdown sequence.
        print("\nKeyboardInterrupt detected. Initiating graceful shutdown...")

        # Signal all running tasks to stop
        shutdown_event.set()

        # Give a short moment for tasks to react and clean up
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
