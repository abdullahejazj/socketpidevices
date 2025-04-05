#!/usr/bin/env node
import { execSync } from 'child_process';
import WebSocket from 'ws';
import net from 'net';
import fs from 'fs/promises';
import readline from 'readline';
import { performance } from 'perf_hooks';

// Configuration
const CONFIG = {
  SERVER_IP: '10.120.233.229',
  PORTS: { tcp: 8080, ws: 8081 },
  TEST_MODES: [
    { type: 'latency', durations: [5, 10, 30], sizes: [64, 1024, 10240] },
    { type: 'throughput', durations: [10, 30], sizes: [102400, 1048576] },
    { type: 'jitter', durations: [30], sizes: [1024] }
  ],
  WARMUP: { iterations: 100, duration: 2000 },
  MONITOR_INTERVAL: 500,
  MAX_LISTENERS: 20
};

class UltimateBenchmark {
  constructor() {
    this.results = {
      system: this.getSystemSpecs(),
      tests: []
    };
    this.currentTest = null;
    this.activeConnections = new Set();
  }

  // System Monitoring
  getSystemSpecs() {
    try {
      return {
        cpu: {
          model: execSync('cat /proc/cpuinfo | grep "Model"').toString().trim(),
          cores: execSync('nproc').toString().trim(),
          freq: execSync('vcgencmd get_config arm_freq').toString().trim()
        },
        memory: execSync('free -h').toString().split('\n')[1],
        os: execSync('cat /etc/os-release | grep PRETTY_NAME').toString().trim(),
        network: execSync('iwconfig wlan0 | grep "Bit Rate"').toString().trim()
      };
    } catch (err) {
      console.error('Error getting system specs:', err);
      return {};
    }
  }

  startMonitoring() {
    this.monitorData = {
      timestamps: [],
      cpu: [], mem: [], temp: [],
      net: { rx: [], tx: [] },
      clock: []
    };

    this.monitorInterval = setInterval(() => {
      try {
        const timestamp = Date.now();
        this.monitorData.timestamps.push(timestamp);
        
        // CPU and Memory
        const cpuMem = execSync(
          "top -bn1 | awk '/Cpu\\(s\\):/ {printf \"%.1f\", 100-$8}' && " +
          "free | awk '/Mem:/ {printf \" %.1f\", $3/$2*100}'"
        ).toString().split(' ').map(parseFloat);
        
        this.monitorData.cpu.push(cpuMem[0]);
        this.monitorData.mem.push(cpuMem[1]);

        // Temperature and Clock
        const tempThrottle = execSync(
          "vcgencmd measure_temp | cut -d= -f2 | cut -d\' -f1 && " +
          "vcgencmd get_throttled"
        ).toString().split('\n');
        
        this.monitorData.temp.push(parseFloat(tempThrottle[0]));
        this.monitorData.clock.push(
          parseInt(execSync('vcgencmd measure_clock arm').toString().split('=')[1])
        );

        // Network
        const netStats = execSync(
          "cat /proc/net/dev | grep wlan0 | awk '{print $2,$3,$10,$11}'"
        ).toString().split(' ').map(Number);
        
        this.monitorData.net.rx.push({
          bytes: netStats[0],
          packets: netStats[1]
        });
        this.monitorData.net.tx.push({
          bytes: netStats[2],
          packets: netStats[3]
        });
      } catch (err) {
        console.error('Monitoring error:', err);
      }
    }, CONFIG.MONITOR_INTERVAL);
  }

  stopMonitoring() {
    clearInterval(this.monitorInterval);
    return this.analyzeMonitorData();
  }

  analyzeMonitorData() {
    const duration = (this.monitorData.timestamps.length * CONFIG.MONITOR_INTERVAL) / 1000;
    const netRxTotal = this.monitorData.net.rx.slice(-1)[0].bytes - this.monitorData.net.rx[0].bytes;
    const netTxTotal = this.monitorData.net.tx.slice(-1)[0].bytes - this.monitorData.net.tx[0].bytes;

    return {
      cpu: this.calcStats(this.monitorData.cpu, '%'),
      mem: this.calcStats(this.monitorData.mem, '%'),
      temp: this.calcStats(this.monitorData.temp, '°C'),
      clock: this.calcStats(this.monitorData.clock.map(c => c/1e6), 'MHz'),
      network: {
        rx_mbps: (netRxTotal * 8 / 1e6) / duration,
        tx_mbps: (netTxTotal * 8 / 1e6) / duration,
        pps: {
          rx: (this.monitorData.net.rx.slice(-1)[0].packets - this.monitorData.net.rx[0].packets) / duration,
          tx: (this.monitorData.net.tx.slice(-1)[0].packets - this.monitorData.net.tx[0].packets) / duration
        }
      },
      throttling: this.checkThrottling()
    };
  }

  checkThrottling() {
    try {
      const throttled = parseInt(execSync('vcgencmd get_throttled').toString().split('=')[1]);
      return {
        under_voltage: !!(throttled & 0x1),
        freq_capped: !!(throttled & 0x2),
        throttled: !!(throttled & 0x4),
        soft_temp_limit: !!(throttled & 0x8)
      };
    } catch {
      return {};
    }
  }

  // Test Execution
  async runAllTests() {
    for (const mode of CONFIG.TEST_MODES) {
      for (const duration of mode.durations) {
        for (const size of mode.sizes) {
          this.currentTest = `${mode.type}_${size}_${duration}`;
          console.log(`\nRunning ${this.currentTest}...`);
          
          const result = await this.runTest({
            protocol: mode.protocol || 'tcp',
            type: mode.type,
            durationSec: duration,
            messageSize: size
          });
          
          this.results.tests.push(result);
          await this.cooldown();
        }
      }
    }
    await this.saveResults();
  }

  async runTest(params) {
    await this[`${params.type}Warmup`](params);
    
    this.startMonitoring();
    const testData = {
      timestamps: [],
      latencies: [],
      throughputs: []
    };

    const startTime = performance.now();
    while ((performance.now() - startTime) < params.durationSec * 1000) {
      const iterStart = performance.now();
      
      if (params.type === 'throughput') {
        const bytesSent = await this.throughputIteration(params);
        testData.throughputs.push(bytesSent / ((performance.now() - iterStart) / 1000));
      } else {
        const latency = await this.latencyIteration(params);
        testData.latencies.push(latency);
      }
      
      testData.timestamps.push(performance.now());
    }

    const metrics = this.stopMonitoring();
    return {
      ...params,
      ...this.analyzeTestData(testData, params.type),
      metrics,
      timestamp: new Date().toISOString()
    };
  }

  // Protocol Implementations
  async latencyWarmup(params) {
    const sock = params.protocol === 'tcp' ? 
      new net.Socket() : 
      new WebSocket(`ws://${CONFIG.SERVER_IP}:${CONFIG.PORTS.ws}`);
    
    sock.setMaxListeners(CONFIG.MAX_LISTENERS);
    this.activeConnections.add(sock);

    try {
      if (params.protocol === 'tcp') {
        sock.connect(CONFIG.PORTS.tcp, CONFIG.SERVER_IP);
        await new Promise(resolve => sock.on('connect', resolve));
      } else {
        await new Promise(resolve => sock.on('open', resolve));
      }

      for (let i = 0; i < CONFIG.WARMUP.iterations; i++) {
        await new Promise(resolve => {
          if (params.protocol === 'tcp') {
            sock.write(Buffer.alloc(params.messageSize), resolve);
            sock.once('data', () => {});
          } else {
            sock.send('x'.repeat(params.messageSize), resolve);
            sock.once('message', () => {});
          }
        });
      }
    } finally {
      this.cleanupConnection(sock);
    }
  }

  async latencyIteration({ protocol, messageSize }) {
    const start = performance.now();
    
    if (protocol === 'tcp') {
      await new Promise(resolve => {
        const sock = new net.Socket();
        sock.setMaxListeners(CONFIG.MAX_LISTENERS);
        this.activeConnections.add(sock);

        const cleanup = () => {
          this.cleanupConnection(sock);
          resolve();
        };

        sock.on('connect', () => {
          sock.write(Buffer.alloc(messageSize), () => {
            sock.once('data', cleanup);
          });
        });

        sock.on('error', cleanup);
        sock.connect(CONFIG.PORTS.tcp, CONFIG.SERVER_IP);
      });
    } else {
      await new Promise(resolve => {
        const ws = new WebSocket(`ws://${CONFIG.SERVER_IP}:${CONFIG.PORTS.ws}`);
        ws.setMaxListeners(CONFIG.MAX_LISTENERS);
        this.activeConnections.add(ws);

        const cleanup = () => {
          this.cleanupConnection(ws);
          resolve();
        };

        ws.on('open', () => {
          ws.send('x'.repeat(messageSize), () => {
            ws.once('message', cleanup);
          });
        });

        ws.on('error', cleanup);
      });
    }
    
    return performance.now() - start;
  }

  async throughputIteration({ protocol, messageSize }) {
    const chunkSize = 1024 * 1024;
    const chunks = Math.ceil(messageSize / chunkSize);
    const lastChunkSize = messageSize % chunkSize || chunkSize;
    let totalSent = 0;

    if (protocol === 'tcp') {
      const sock = new net.Socket();
      sock.setMaxListeners(CONFIG.MAX_LISTENERS);
      this.activeConnections.add(sock);

      try {
        sock.connect(CONFIG.PORTS.tcp, CONFIG.SERVER_IP);
        await new Promise(resolve => sock.on('connect', resolve));

        for (let i = 0; i < chunks; i++) {
          const size = i === chunks - 1 ? lastChunkSize : chunkSize;
          await new Promise(resolve => {
            sock.write(Buffer.alloc(size), resolve);
            sock.once('data', () => {});
          });
          totalSent += size;
        }
      } finally {
        this.cleanupConnection(sock);
      }
    } else {
      const ws = new WebSocket(`ws://${CONFIG.SERVER_IP}:${CONFIG.PORTS.ws}`);
      ws.setMaxListeners(CONFIG.MAX_LISTENERS);
      this.activeConnections.add(ws);

      try {
        await new Promise(resolve => ws.on('open', resolve));

        for (let i = 0; i < chunks; i++) {
          const size = i === chunks - 1 ? lastChunkSize : chunkSize;
          await new Promise(resolve => {
            ws.send('x'.repeat(size), resolve);
            ws.once('message', () => {});
          });
          totalSent += size;
        }
      } finally {
        this.cleanupConnection(ws);
      }
    }

    return totalSent;
  }

  cleanupConnection(conn) {
    try {
      if (conn instanceof net.Socket) {
        conn.removeAllListeners();
        conn.destroy();
      } else if (conn instanceof WebSocket) {
        conn.removeAllListeners();
        conn.terminate();
      }
      this.activeConnections.delete(conn);
    } catch (err) {
      console.error('Cleanup error:', err);
    }
  }

  // Analysis Utilities
  analyzeTestData(data, testType) {
    const result = {};
    
    if (testType === 'throughput') {
      result.throughput = {
        avg_mbps: this.calcStats(data.throughputs.map(t => t * 8 / 1e6)).avg,
        total_bytes: data.throughputs.reduce((a, b) => a + b, 0)
      };
    } else {
      const cleanLatencies = this.removeOutliers(data.latencies);
      result.latency = this.calcStats(cleanLatencies, 'ms');
      
      if (testType === 'jitter') {
        result.jitter = this.calculateJitter(cleanLatencies);
      }
    }
    
    return result;
  }

  calculateJitter(latencies) {
    const diffs = [];
    for (let i = 1; i < latencies.length; i++) {
      diffs.push(Math.abs(latencies[i] - latencies[i-1]));
    }
    return this.calcStats(diffs, 'ms');
  }

  calcStats(values, unit = '') {
    if (!values.length) return { avg: 0, min: 0, max: 0, unit };
    
    const avg = values.reduce((a, b) => a + b, 0) / values.length;
    const sorted = [...values].sort((a, b) => a - b);
    
    return {
      avg: parseFloat(avg.toFixed(2)),
      min: parseFloat(sorted[0].toFixed(2)),
      max: parseFloat(sorted[sorted.length - 1].toFixed(2)),
      p50: parseFloat(sorted[Math.floor(sorted.length * 0.5)].toFixed(2)),
      p95: parseFloat(sorted[Math.floor(sorted.length * 0.95)].toFixed(2)),
      p99: parseFloat(sorted[Math.floor(sorted.length * 0.99)].toFixed(2)),
      std: parseFloat(
        Math.sqrt(values.map(x => Math.pow(x - avg, 2)).reduce((a, b) => a + b) / values.length
      ).toFixed(2)),
      unit
    };
  }

  removeOutliers(values) {
    if (values.length < 10) return values;
    const q1 = this.percentile(values, 25);
    const q3 = this.percentile(values, 75);
    const iqr = q3 - q1;
    return values.filter(x => 
      x >= q1 - 1.5*iqr && 
      x <= q3 + 1.5*iqr
    );
  }

  percentile(arr, p) {
    const sorted = [...arr].sort((a, b) => a - b);
    const pos = (sorted.length - 1) * p / 100;
    const base = Math.floor(pos);
    const rest = pos - base;
    return sorted[base] + (rest * (sorted[base + 1] - sorted[base]));
  }

  async cooldown() {
    console.log('Cooling down...');
    await new Promise(resolve => setTimeout(resolve, CONFIG.WARMUP.duration));
  }

  async saveResults() {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `benchmark_results_${timestamp}.json`;
    await fs.writeFile(filename, JSON.stringify(this.results, null, 2));
    console.log(`Results saved to ${filename}`);
  }

  async menu() {
    console.clear();
    console.log('=== Ultimate Raspberry Pi Network Benchmark ===');
    console.log(`Target Server: ${CONFIG.SERVER_IP}`);
    console.log('1) Run Complete Test Suite');
    console.log('2) Configure Server IP');
    console.log('3) Exit');

    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    const choice = await new Promise(resolve => rl.question('Select option: ', resolve));
    rl.close();

    switch (choice) {
      case '1':
        await this.runAllTests();
        break;
      case '2':
        CONFIG.SERVER_IP = await new Promise(resolve => {
          const rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
          });
          rl.question('Enter new server IP: ', (ip) => {
            rl.close();
            resolve(ip);
          });
        });
        break;
      case '3':
        process.exit(0);
      default:
        console.log('Invalid choice');
    }

    await new Promise(resolve => setTimeout(resolve, 1000));
    this.menu();
  }
}

// Run the benchmark
new UltimateBenchmark().menu().catch(console.error);