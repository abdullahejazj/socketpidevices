import { WebSocketServer } from 'ws';
import os from 'os';
import fs from 'fs/promises';
import process from 'process';

class MetricsCollector {
    constructor(testDuration) {
        this.startTime = Date.now();
        this.testDuration = testDuration * 60 * 1000;
        this.metrics = {
            connections: 0,
            messagesReceived: 0,
            messagesSent: 0,
            latencies: [],
            messageSizes: []
        };
    }

    async saveMetrics() {
        const duration = (Date.now() - this.startTime) / 1000;
        const summary = {
            testDuration: this.testDuration / 60000,
            actualDuration: duration,
            ...this.metrics,
            system: {
                cpu: process.cpuUsage(),
                memory: process.memoryUsage(),
                load: os.loadavg()
            }
        };

        await fs.writeFile(
            `server_metrics_${this.testDuration}min.json`,
            JSON.stringify(summary, null, 2)
        );
    }
}

const startServer = async (testDuration) => {
    const metrics = new MetricsCollector(testDuration);
    const server = new WebSocketServer({ port: 8080 });

    server.on('connection', (ws) => {
        metrics.metrics.connections++;
        
        ws.on('message', (data) => {
            const receiveTime = Date.now();
            const message = data.toString();
            const [payload, sendTime] = message.split('|');
            
            metrics.metrics.messagesReceived++;
            metrics.metrics.messageSizes.push(data.length);
            
            // Calculate latency
            const latency = receiveTime - parseInt(sendTime);
            metrics.metrics.latencies.push(latency);
            
            // Send response
            const response = `${payload}|${receiveTime}`;
            ws.send(response);
            metrics.metrics.messagesSent++;
        });

        ws.on('close', () => {
            metrics.metrics.connections--;
        });
    });

    console.log(`WebSocket server running for ${testDuration} minutes...`);
    
    setTimeout(async () => {
        server.close();
        await metrics.saveMetrics();
        console.log('Server stopped and metrics saved');
        process.exit(0);
    }, metrics.testDuration);
};

// Get duration from command line or default to 2 minutes
const duration = parseInt(process.argv[2]) || 2;
startServer(duration).catch(console.error);