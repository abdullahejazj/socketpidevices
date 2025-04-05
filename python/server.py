import socket
import threading
import time
import psutil
import os
import subprocess
import json
from websocket import WebSocketServer

class SocketServer:
    def __init__(self):
        self.stats = {
            'startTime': time.time(),
            'connections': {
                'tcp': set(),
                'ws': set(),
                'total': 0
            },
            'metrics': {
                'bytesReceived': 0,
                'bytesSent': 0,
                'packetsReceived': 0,
                'packetsSent': 0
            }
        }

        # TCP Server
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server.bind(('0.0.0.0', 8080))
        self.tcp_server.listen(5)

        # WebSocket Server
        self.ws_server = WebSocketServer('0.0.0.0', 8081, self.on_ws_connect)

    def on_ws_connect(self, client):
        self.stats['connections']['ws'].add(client)

        def on_message(message):
            self.stats['metrics']['bytesReceived'] += len(message)
            self.stats['metrics']['packetsReceived'] += 1
            client.send(message)
            self.stats['metrics']['bytesSent'] += len(message)
            self.stats['metrics']['packetsSent'] += 1

        client.on_message = on_message
        client.on_close = lambda: self.stats['connections']['ws'].remove(client)

    def start(self):
        print("Starting TCP and WebSocket servers...")

        # Start TCP server in a separate thread
        def handle_tcp():
            while True:
                client, addr = self.tcp_server.accept()
                self.stats['connections']['tcp'].add(client)
                print(f"New TCP connection from {addr}")
                self.handle_tcp_client(client)

        threading.Thread(target=handle_tcp, daemon=True).start()

        # Start WebSocket server
        self.ws_server.start()

    def handle_tcp_client(self, client):
        while True:
            try:
                data = client.recv(1024)
                if not data:
                    break
                self.stats['metrics']['bytesReceived'] += len(data)
                self.stats['metrics']['packetsReceived'] += 1
                client.send(data)
                self.stats['metrics']['bytesSent'] += len(data)
                self.stats['metrics']['packetsSent'] += 1
            except:
                break
        self.stats['connections']['tcp'].remove(client)
        client.close()

    def get_metrics(self):
        uptime = time.time() - self.stats['startTime']
        return {
            'uptime': uptime,
            'connections': {
                'tcp': len(self.stats['connections']['tcp']),
                'ws': len(self.stats['connections']['ws']),
                'total': self.stats['connections']['tcp'] + self.stats['connections']['ws']
            },
            'throughput': {
                'bytes_per_sec': {
                    'in': self.stats['metrics']['bytesReceived'] / uptime,
                    'out': self.stats['metrics']['bytesSent'] / uptime
                },
                'packets_per_sec': {
                    'in': self.stats['metrics']['packetsReceived'] / uptime,
                    'out': self.stats['metrics']['packetsSent'] / uptime
                }
            },
            'system': self.get_system_info()
        }

    def get_system_info(self):
        return {
            'load': os.getloadavg(),
            'memory': {
                'free': psutil.virtual_memory().available,
                'total': psutil.virtual_memory().total,
                'usage': psutil.virtual_memory().percent
            },
            'cpu': {
                'model': psutil.cpu_freq().current,
                'speed': psutil.cpu_freq().current,
                'count': psutil.cpu_count()
            },
            'temperature': self.get_cpu_temperature()
        }

    def get_cpu_temperature(self):
        try:
            if os.name == 'posix':
                temp = subprocess.check_output(['vcgencmd', 'measure_temp']).decode('utf-8')
                return float(temp.split('=')[1].split("'")[0])
            return None
        except:
            return None

if __name__ == '__main__':
    server = SocketServer()
    server.start()

    while True:
        time.sleep(1)
        print(json.dumps(server.get_metrics(), indent=2))
