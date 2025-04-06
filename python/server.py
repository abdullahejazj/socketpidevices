import asyncio
import json
import os
import socket
import subprocess
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import websockets
import time 
# Configuration - matches Node.js version exactly
CONFIG = {
    'PORTS': {'tcp': 8080, 'ws': 8081},
    'MAX_LISTENERS': 30
}

class SocketServer:
    def __init__(self):
        self.stats = {
            'startTime': datetime.now(),
            'connections': {
                'tcp': set(),
                'ws': set()
            },
            'metrics': {
                'bytesReceived': 0,
                'bytesSent': 0,
                'packetsReceived': 0,
                'packetsSent': 0
            }
        }
        
        # Start TCP server
        self.tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server.bind(('0.0.0.0', CONFIG['PORTS']['tcp']))
        self.tcp_server.listen()
        
        def tcp_server_loop():
            with ThreadPoolExecutor() as executor:
                while True:
                    conn, addr = self.tcp_server.accept()
                    self.stats['connections']['tcp'].add(conn)
                    
                    def handle_tcp_client(client_conn):
                        try:
                            while True:
                                data = client_conn.recv(1024 * 1024)  # 1MB max per read
                                if not data:
                                    break
                                
                                self.stats['metrics']['bytesReceived'] += len(data)
                                self.stats['metrics']['packetsReceived'] += 1
                                client_conn.send(data)
                                self.stats['metrics']['bytesSent'] += len(data)
                                self.stats['metrics']['packetsSent'] += 1
                        except:
                            pass
                        finally:
                            self.stats['connections']['tcp'].discard(client_conn)
                            client_conn.close()
                    
                    executor.submit(handle_tcp_client, conn)
        
        self.tcp_thread = threading.Thread(target=tcp_server_loop)
        self.tcp_thread.daemon = True
        self.tcp_thread.start()
        
        # Start WebSocket server
        async def ws_handler(websocket, path):
            self.stats['connections']['ws'].add(websocket)
            try:
                async for message in websocket:
                    self.stats['metrics']['bytesReceived'] += len(message)
                    self.stats['metrics']['packetsReceived'] += 1
                    await websocket.send(message)
                    self.stats['metrics']['bytesSent'] += len(message)
                    self.stats['metrics']['packetsSent'] += 1
            except:
                pass
            finally:
                self.stats['connections']['ws'].discard(websocket)
        
        async def http_handler(reader, writer):
            try:
                request = (await reader.read(1024)).decode()
                if 'GET /metrics' in request:
                    response = json.dumps(self.get_metrics(), indent=2).encode()
                    writer.write(b'HTTP/1.1 200 OK\r\n')
                    writer.write(b'Content-Type: application/json\r\n')
                    writer.write(f'Content-Length: {len(response)}\r\n'.encode())
                    writer.write(b'\r\n')
                    writer.write(response)
                else:
                    writer.write(b'HTTP/1.1 404 Not Found\r\n\r\n')
            finally:
                writer.close()
        
        async def start_servers():
            ws_server = await websockets.serve(
                ws_handler,
                '0.0.0.0',
                CONFIG['PORTS']['ws'],
                max_size=100 * 1024 * 1024  # 100MB max message size
            )
            
            http_server = await asyncio.start_server(
                http_handler,
                '0.0.0.0',
                CONFIG['PORTS']['ws']
            )
            
            await asyncio.gather(
                ws_server.wait_closed(),
                http_server.wait_closed()
            )
        
        self.server_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.server_loop)
        self.server_thread = threading.Thread(target=self.server_loop.run_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        asyncio.run_coroutine_threadsafe(start_servers(), self.server_loop)
        
        print("""
  ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗ 
  ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗
  ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝
  ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗
  ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║
  ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
  
  TCP Server running on port 8080
  WebSocket Server running on port 8081
  Metrics available at http://[YOUR_IP]:8081/metrics
""")
    
    def get_metrics(self):
        uptime = (datetime.now() - self.stats['startTime']).total_seconds()
        return {
            'uptime': uptime,
            'connections': {
                'tcp': len(self.stats['connections']['tcp']),
                'ws': len(self.stats['connections']['ws']),
                'total': len(self.stats['connections']['tcp']) + len(self.stats['connections']['ws'])
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
            'system': {
                'load': os.getloadavg(),
                'memory': {
                    'free': os.freemem(),
                    'total': os.totalmem(),
                    'usage': (1 - (os.freemem() / os.totalmem())) * 100
                },
                'cpu': {
                    'model': ' '.join(subprocess.check_output('cat /proc/cpuinfo | grep "model name"', shell=True).decode().split(':')[-1].strip()),
                    'speed': float(subprocess.check_output('vcgencmd measure_clock arm | cut -d= -f2', shell=True).decode().strip()) / 1000000,
                    'count': os.cpu_count()
                },
                'temperature': self.get_cpu_temperature()
            }
        }
    
    def get_cpu_temperature(self):
        try:
            temp = subprocess.check_output('vcgencmd measure_temp', shell=True).decode()
            return float(temp.split('=')[1].split("'")[0])
        except:
            return None

if __name__ == '__main__':
    server = SocketServer()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServer shutting down gracefully...")