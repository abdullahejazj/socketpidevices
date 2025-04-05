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
        tcp: new Set(),
        ws: new Set(),
        get total() {
          return this.tcp.size + this.ws.size;
        }
      },
      metrics: {
        bytesReceived: 0,
        bytesSent: 0,
        packetsReceived: 0,
        packetsSent: 0
      }
    };

    // TCP Server
    this.tcpServer = net.createServer(socket => {
      socket.setMaxListeners(20);
      this.stats.connections.tcp.add(socket);

      socket.on('data', data => {
        this.stats.metrics.bytesReceived += data.length;
        this.stats.metrics.packetsReceived++;
        socket.write(data);
        this.stats.metrics.bytesSent += data.length;
        this.stats.metrics.packetsSent++;
      });

      socket.on('close', () => {
        this.stats.connections.tcp.delete(socket);
      });

      socket.on('error', () => {
        this.stats.connections.tcp.delete(socket);
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

    // WebSocket Server
    this.wsServer = new WebSocketServer({ 
      server: this.httpServer,
      maxPayload: 100 * 1024 * 1024 // 100MB max message size
    });

    this.wsServer.on('connection', ws => {
      ws.setMaxListeners(20);
      this.stats.connections.ws.add(ws);

      ws.on('message', message => {
        const msgString = message.toString();
        this.stats.metrics.bytesReceived += Buffer.byteLength(msgString);
        this.stats.metrics.packetsReceived++;
        ws.send(msgString);
        this.stats.metrics.bytesSent += Buffer.byteLength(msgString);
        this.stats.metrics.packetsSent++;
      });

      ws.on('close', () => {
        this.stats.connections.ws.delete(ws);
      });

      ws.on('error', () => {
        this.stats.connections.ws.delete(ws);
      });
    });

    this.httpServer.listen(8081, '0.0.0.0');
  }

  getMetrics() {
    const uptime = process.uptime();
    return {
      uptime,
      connections: {
        tcp: this.stats.connections.tcp.size,
        ws: this.stats.connections.ws.size,
        total: this.stats.connections.total
      },
      throughput: {
        bytes_per_sec: {
          in: this.stats.metrics.bytesReceived / uptime,
          out: this.stats.metrics.bytesSent / uptime
        },
        packets_per_sec: {
          in: this.stats.metrics.packetsReceived / uptime,
          out: this.stats.metrics.packetsSent / uptime
        }
      },
      system: {
        load: os.loadavg(),
        memory: {
          free: os.freemem(),
          total: os.totalmem(),
          usage: (1 - (os.freemem() / os.totalmem())) * 100
        },
        cpu: {
          model: os.cpus()[0].model,
          speed: os.cpus()[0].speed,
          count: os.cpus().length
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

// Start server
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