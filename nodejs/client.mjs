import WebSocket from 'ws';
import os from 'os';
import fs from 'fs/promises';
import process from 'process';

class ClientMetrics {
    constructor(testDuration) {
        this.startTime = Date.now();
        this.testDuration = testDuration * 60 * 1000;
        this.ws = new WebSocket('ws://127.0.0.1:8080');
        this.metrics = {
            sentMessages: 0,
            receivedMessages: 0,
            latencies: [],
            jitters: [],
            lastLatency: 0,
            errors: 0,
            messageSizes: []
        };
    }

    async saveMetrics() {
        const duration = (Date.now() - this.startTime) / 1000;
        const stats = {
            throughput: this.metrics.receivedMessages / duration,
            packetLoss: ((this.metrics.sentMessages - this.metrics.receivedMessages) / 
                       this.metrics.sentMessages) * 100,
            avgLatency: this.metrics.latencies.reduce((a, b) => a + b, 0) / 
                       this.metrics.latencies.length || 0,
            avgJitter: this.metrics.jitters.reduce((a, b) => a + b, 0) / 
                      this.metrics.jitters.length || 0
        };

        const result = {
            testDuration: this.testDuration / 60000,
            actualDuration: duration,
            stats,
            system: {
                cpu: process.cpuUsage(),
                memory: process.memoryUsage(),
                load: os.loadavg()
            },
            rawMetrics: this.metrics
        };

        await fs.writeFile(
            `client_metrics_${this.testDuration}min.json`,
            JSON.stringify(result, null, 2)
        );
    }

    startSending() {
        this.interval = setInterval(() => {
            if (this.ws.readyState === WebSocket.OPEN) {
                const message = `TestMsg${this.metrics.sentMessages}|${Date.now()}`;
                this.ws.send(message);
                this.metrics.sentMessages++;
                this.metrics.messageSizes.push(message.length);
            }
        }, 10); // 100 messages/second
    }

    async run() {
        return new Promise((resolve) => {
            this.ws.on('open', () => {
                console.log('Connected to server');
                this.startSending();
                
                setTimeout(async () => {
                    clearInterval(this.interval);
                    this.ws.close();
                    await this.saveMetrics();
                    resolve();
                }, this.testDuration);
            });

            this.ws.on('message', (data) => {
                const receiveTime = Date.now();
                const serverTime = parseInt(data.toString().split('|')[1]);
                const latency = receiveTime - serverTime;
                
                this.metrics.receivedMessages++;
                this.metrics.latencies.push(latency);
                
                if (this.metrics.lastLatency > 0) {
                    this.metrics.jitters.push(Math.abs(latency - this.metrics.lastLatency));
                }
                this.metrics.lastLatency = latency;
            });

            this.ws.on('error', (err) => {
                this.metrics.errors++;
                console.error('WebSocket error:', err);
            });
        });
    }
}

const duration = parseInt(process.argv[2]) || 2;
const client = new ClientMetrics(duration);
client.run().catch(console.error);