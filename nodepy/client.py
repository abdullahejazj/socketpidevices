import asyncio
import time
import csv
import os

HOST = "localhost"
PORT = 8888
MESSAGE_SIZE = 64
INTERVAL = 0.05
NUM_MESSAGES = 1000

csv_file = "python_test_results.csv"

if not os.path.exists(csv_file):
    with open(csv_file, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Sequence", "Sent Time", "Received Time", "RTT (ms)", "Jitter (ms)", "Throughput (kbps)"])

async def send_messages():
    reader, writer = await asyncio.open_connection(HOST, PORT)
    print(f"Connected to {HOST}:{PORT}")

    prev_rtt = None
    total_data_sent = 0
    start_time = time.time()

    for seq in range(1, NUM_MESSAGES + 1):
        send_time = time.time()
        message = f"{seq}|{send_time}|{MESSAGE_SIZE}".ljust(MESSAGE_SIZE).encode()
        writer.write(message)
        await writer.drain()

        data = await reader.read(1024)
        recv_time = time.time()
        
        if data:
            rtt = (recv_time - send_time) * 1000
            jitter = abs(rtt - prev_rtt) if prev_rtt else 0
            prev_rtt = rtt

            total_data_sent += len(data)
            elapsed_time = recv_time - start_time
            throughput = (total_data_sent * 8) / (elapsed_time * 1000) if elapsed_time > 0 else 0

            with open(csv_file, "a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([seq, send_time, recv_time, rtt, jitter, throughput])

            await asyncio.sleep(INTERVAL)

    print("Test completed.")
    writer.close()
    await writer.wait_closed()

asyncio.run(send_messages())
