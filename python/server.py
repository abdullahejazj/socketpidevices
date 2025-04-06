import asyncio
import socket
import json
import psutil
import platform
import time  # Added missing import
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import websockets
from aiohttp import web

class NetworkServer:
    def __init__(self):
        self.stats = {
            'start_time': datetime.now().isoformat(),
            'connections': {
                'tcp': set(),
                'ws': set(),
                'total': 0
            },
            'metrics': {
                'bytes_received': 0,
                'bytes_sent': 0,
                'packets_received': 0,
                'packets_sent': 0,
                'avg_processing_time': 0
            }
        }
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.loop = asyncio.get_event_loop()

    def get_metrics(self):
        """Return current server metrics"""
        uptime = (datetime.now() - datetime.fromisoformat(self.stats['start_time'])).total_seconds()
        return {
            'uptime': uptime,
            'connections': {
                'tcp': len(self.stats['connections']['tcp']),
                'ws': len(self.stats['connections']['ws']),
                'total': len(self.stats['connections']['tcp']) + len(self.stats['connections']['ws'])
            },
            'throughput': {
                'bytes_per_sec': {
                    'in': self.stats['metrics']['bytes_received'] / uptime if uptime > 0 else 0,
                    'out': self.stats['metrics']['bytes_sent'] / uptime if uptime > 0 else 0
                },
                'packets_per_sec': {
                    'in': self.stats['metrics']['packets_received'] / uptime if uptime > 0 else 0,
                    'out': self.stats['metrics']['packets_sent'] / uptime if uptime > 0 else 0
                }
            },
            'system': {
                'load': [x / psutil.cpu_count() for x in psutil.getloadavg()],
                'memory': {
                    'free': psutil.virtual_memory().available,
                    'total': psutil.virtual_memory().total,
                    'usage': psutil.virtual_memory().percent
                },
                'cpu': {
                    'model': platform.processor(),
                    'count': psutil.cpu_count(logical=False)
                }
            },
            'processing': {
                'avg_time': self.stats['metrics']['avg_processing_time']
            }
        }

    async def handle_tcp_client(self, reader, writer):
        """Handle incoming TCP connections"""
        client_addr = writer.get_extra_info('peername')
        self.stats['connections']['tcp'].add(client_addr)
        self.stats['connections']['total'] += 1
        
        try:
            while True:
                start_time = time.time()  # Now using the imported time module
                data = await reader.read(4096)
                if not data:
                    break
                    
                self.stats['metrics']['bytes_received'] += len(data)
                self.stats['metrics']['packets_received'] += 1
                
                # Calculate processing time
                processing_time = time.time() - start_time
                self.stats['metrics']['avg_processing_time'] = (
                    self.stats['metrics']['avg_processing_time'] * 0.9 + processing_time * 0.1
                )
                
                # Echo back
                writer.write(data)
                await writer.drain()
                
                self.stats['metrics']['bytes_sent'] += len(data)
                self.stats['metrics']['packets_sent'] += 1
                
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self.stats['connections']['tcp'].remove(client_addr)
            self.stats['connections']['total'] -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def handle_websocket(self, websocket, path):
        """Handle WebSocket connections"""
        client_addr = websocket.remote_address
        self.stats['connections']['ws'].add(client_addr)
        self.stats['connections']['total'] += 1
        
        try:
            async for message in websocket:
                start_time = time.time()
                msg_size = len(message)
                self.stats['metrics']['bytes_received'] += msg_size
                self.stats['metrics']['packets_received'] += 1
                
                # Calculate processing time
                processing_time = time.time() - start_time
                self.stats['metrics']['avg_processing_time'] = (
                    self.stats['metrics']['avg_processing_time'] * 0.9 + processing_time * 0.1
                )
                
                await websocket.send(message)
                self.stats['metrics']['bytes_sent'] += msg_size
                self.stats['metrics']['packets_sent'] += 1
                
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            self.stats['connections']['ws'].remove(client_addr)
            self.stats['connections']['total'] -= 1

    async def metrics_handler(self, request):
        """HTTP handler for metrics endpoint"""
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
        return web.Response(
            text=json.dumps(self.get_metrics(), indent=2),
            headers=headers
        )

    async def start_servers(self):
        """Start all server components"""
        # TCP Server
        tcp_server = await asyncio.start_server(
            self.handle_tcp_client,
            '0.0.0.0',
            8080,
            reuse_port=True,
            backlog=1000
        )
        
        # WebSocket Server
        ws_server = await websockets.serve(
            self.handle_websocket,
            '0.0.0.0',
            8081,
            max_size=100*1024*1024,
            ping_interval=None
        )
        
        # HTTP Metrics Server
        app = web.Application()
        app.add_routes([web.get('/metrics', self.metrics_handler)])
        runner = web.AppRunner(app)
        await runner.setup()
        http_site = web.TCPSite(runner, '0.0.0.0', 8082)
        await http_site.start()
        
        print("""
          _____ _____ _____ _____ _____ _____ 
         / ____|  __ \_   _/ ____|_   _/ ____|
        | (___ | |__) || || |      | || |     
         \___ \|  ___/ | || |      | || |     
         ____) | |    _| || |____ _| || |____ 
        |_____/|_|   |_____\_____|_____\_____|
        
        TCP Server running on port 8080
        WebSocket Server running on port 8081
        Metrics available at http://[YOUR_IP]:8082/metrics
        """)
        
        await asyncio.Future()  # Run forever

    def run(self):
        """Start the server"""
        try:
            asyncio.run(self.start_servers())
        except KeyboardInterrupt:
            print("\nServer shutting down gracefully...")

if __name__ == "__main__":
    server = NetworkServer()
    server.run()