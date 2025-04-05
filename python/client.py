import socket
import time
import subprocess
import psutil
import websocket
from threading import Thread
import json
import random
import os

# Configuration
SERVER_IP = '10.42.0.1'  # Server IP
PORTS = {'tcp': 8080, 'ws': 8081}  # Server ports for TCP and WebSocket
TEST_MODES = [
    {'type': 'latency', 'durations': [5, 10, 30], 'sizes': [64, 1024, 10240]},
    {'type': 'throughput', 'durations': [10, 30], 'sizes': [102400, 1048576]},
    {'type': 'jitter', 'durations': [30], 'sizes': [1024]}
]
WARMUP = {'iterations': 100, 'duration': 2000}  # Warmup configurations
MONITOR_INTERVAL = 500  # Interval for system monitoring in ms
MAX_LISTENERS = 30  # Max number of listeners for WebSocket
COOLDOWN_TIME = 10000  # Cooldown time in ms
TEST_RUNS = 10  # Number of test runs

# System Specs
def get_system_specs():
    try:
        return {
            'cpu': {
                'model': subprocess.check_output(['cat', '/proc/cpuinfo']).decode().strip(),
                'cores': psutil.cpu_count(),
                'freq': subprocess.check_output(['vcgencmd', 'get_config', 'arm_freq']).decode().strip()
            },
            'memory': psutil.virtual_memory(),
            'os': subprocess.check_output(['cat', '/etc/os-release']).decode().strip(),
            'network': subprocess.check_output(['iwconfig', 'wlan0']).decode().strip()
        }
    except Exception as e:
        print("Error getting system specs:", e)
        return {}

def start_monitoring():
    monitor_data = {'cpu': [], 'mem': [], 'net': {'rx': [], 'tx': []}, 'clock': []}
    
    def monitor_system():
        while True:
            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent
            net_io = psutil.net_io_counters()
            
            monitor_data['cpu'].append(cpu_usage)
            monitor_data['mem'].append(memory_usage)
            monitor_data['net']['rx'].append(net_io.bytes_recv)
            monitor_data['net']['tx'].append(net_io.bytes_sent)
            time.sleep(MONITOR_INTERVAL / 1000)
    
    monitor_thread = Thread(target=monitor_system, daemon=True)
    monitor_thread.start()

# Connect to TCP server
def connect_tcp():
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((SERVER_IP, PORTS['tcp']))
    return tcp_socket

# WebSocket callback functions
def on_message(ws, message):
    print(f"Received message: {message}")
    # Simulate data processing
    ws.send(message)

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    print("### opened ###")

# Connect to WebSocket server
def connect_ws():
    ws = websocket.WebSocketApp(f"ws://{SERVER_IP}:{PORTS['ws']}",
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    return ws

# Perform latency test
def test_latency(socket_type, duration, size):
    print(f"Starting {socket_type} latency test for {duration}s with message size {size} bytes")
    start_time = time.time()
    total_latency = 0
    count = 0

    if socket_type == 'tcp':
        sock = connect_tcp()
    else:
        ws = connect_ws()
        ws.run_forever()

    while time.time() - start_time < duration:
        if socket_type == 'tcp':
            msg = random.randbytes(size)
            start = time.time()
            sock.send(msg)
            sock.recv(size)
            total_latency += time.time() - start
            count += 1
        elif socket_type == 'ws':
            msg = random.randbytes(size)
            start = time.time()
            ws.send(msg)
            ws.recv()
            total_latency += time.time() - start
            count += 1

    avg_latency = total_latency / count if count else 0
    print(f"{socket_type} latency test completed: Average latency = {avg_latency:.4f} seconds")
    return avg_latency

# Perform throughput test
def test_throughput(socket_type, duration, size):
    print(f"Starting {socket_type} throughput test for {duration}s with message size {size} bytes")
    start_time = time.time()
    total_bytes = 0
    count = 0

    if socket_type == 'tcp':
        sock = connect_tcp()
    else:
        ws = connect_ws()
        ws.run_forever()

    while time.time() - start_time < duration:
        if socket_type == 'tcp':
            msg = random.randbytes(size)
            sock.send(msg)
            total_bytes += len(msg)
            count += 1
        elif socket_type == 'ws':
            msg = random.randbytes(size)
            ws.send(msg)
            total_bytes += len(msg)
            count += 1

    throughput = total_bytes / (time.time() - start_time)  # bytes per second
    print(f"{socket_type} throughput test completed: Throughput = {throughput:.2f} bytes/sec")
    return throughput

# Perform jitter test
def test_jitter(socket_type, duration, size):
    print(f"Starting {socket_type} jitter test for {duration}s with message size {size} bytes")
    start_time = time.time()
    last_time = None
    jitter = []

    if socket_type == 'tcp':
        sock = connect_tcp()
    else:
        ws = connect_ws()
        ws.run_forever()

    while time.time() - start_time < duration:
        if socket_type == 'tcp':
            msg = random.randbytes(size)
            sock.send(msg)
            response_time = time.time()
            if last_time is not None:
                jitter.append(response_time - last_time)
            last_time = response_time
        elif socket_type == 'ws':
            msg = random.randbytes(size)
            ws.send(msg)
            response_time = time.time()
            if last_time is not None:
                jitter.append(response_time - last_time)
            last_time = response_time

    avg_jitter = sum(jitter) / len(jitter) if jitter else 0
    print(f"{socket_type} jitter test completed: Average jitter = {avg_jitter:.4f} seconds")
    return avg_jitter

# Running tests
def run_tests():
    print("Starting performance tests...")
    results = {}

    for mode in TEST_MODES:
        for duration in mode['durations']:
            for size in mode['sizes']:
                for socket_type in ['tcp', 'ws']:
                    if mode['type'] == 'latency':
                        result = test_latency(socket_type, duration, size)
                    elif mode['type'] == 'throughput':
                        result = test_throughput(socket_type, duration, size)
                    elif mode['type'] == 'jitter':
                        result = test_jitter(socket_type, duration, size)

                    results[f"{socket_type}_{mode['type']}_{duration}s_{size}bytes"] = result
                time.sleep(1)  # Sleep between test runs

    print("Test results:", json.dumps(results, indent=2))

if __name__ == "__main__":
    start_monitoring()
    run_tests()
