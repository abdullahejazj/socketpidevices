#!/usr/bin/env node
import net from 'net';
import { WebSocketServer } from 'ws';
import http from 'http';
import os from 'os';
import { execSync } from 'child_process';

class SocketServer {
  constructor() {
    this.stats = {
      startTime: new Date(),
      connections: {
        tcp: 0,
        ws: 0,
        total: 0
      },
      metrics: {
        bytesReceived: 0,
        bytesSent: 0,
        packetsReceived: 0,
        packetsSent: 0
      }
    };

    // Start TCP Server
    this.tcpServer = net.createServer(socket => {
      this.stats.connections.tcp++;
      this.stats.connections.total++;

      socket.on('data', data => {
        this.stats.metrics.bytesReceived += data.length;
        this.stats.metrics.packetsReceived++;
        socket.write(data); // Echo back
        this.stats.metrics.bytesSent += data.length;
        this.stats.metrics.packetsSent++;
      });

      socket.on('close', () => {
        this.stats.connections.tcp--;
        this.stats.connections.total--;
      });
    }).listen(8080, '0.0.0.0');

    // HTTP Server for WebSocket and metrics
    this.httpServer = http.createServer((req, res) => {
      if (req.url === '/metrics') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(this.getMetrics(), null, 2));
      } else {
        res.writeHead(404);
        res.end();
      }
    });

    // WebSocket Server (updated initialization)
    this.wsServer = new WebSocketServer({ server: this.httpServer });
    this.wsServer.on('connection', ws => {
      this.stats.connections.ws++;
      this.stats.connections.total++;

      ws.on('message', message => {
        const msgString = message.toString();
        this.stats.metrics.bytesReceived += Buffer.byteLength(msgString);
        this.stats.metrics.packetsReceived++;
        ws.send(msgString); // Echo back
        this.stats.metrics.bytesSent += Buffer.byteLength(msgString);
        this.stats.metrics.packetsSent++;
      });

      ws.on('close', () => {
        this.stats.connections.ws--;
        this.stats.connections.total--;
      });
    });

    this.httpServer.listen(8081, '0.0.0.0');
  }

  getMetrics() {
    return {
      uptime: process.uptime(),
      connections: this.stats.connections,
      throughput: {
        bytes_per_sec: {
          in: this.stats.metrics.bytesReceived / process.uptime(),
          out: this.stats.metrics.bytesSent / process.uptime()
        },
        packets_per_sec: {
          in: this.stats.metrics.packetsReceived / process.uptime(),
          out: this.stats.metrics.packetsSent / process.uptime()
        }
      },
      system: {
        load: os.loadavg(),
        memory: {
          free: os.freemem(),
          total: os.totalmem()
        },
        cpu: {
          model: os.cpus()[0].model,
          speed: os.cpus()[0].speed
        },
        temperature: this.getCPUTemperature()
      }
    };
  }

  getCPUTemperature() {
    try {
      if (process.platform === 'linux') {
        const temp = execSync('vcgencmd measure_temp').toString();
        return parseFloat(temp.match(/\d+\.\d+/)[0]);
      }
      return null;
    } catch {
      return null;
    }
  }
}

// Start server with monitoring
new SocketServer();

console.log(`
  ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗ 
  ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗
  ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝
  ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗
  ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║
  ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
  
  TCP Server running on port 8080
  WebSocket Server running on port 8081
  Metrics available at http://[YOUR_IP]:8081/metrics
`);

process.on('SIGINT', () => {
  console.log('\nServer shutting down gracefully...');
  process.exit();
});