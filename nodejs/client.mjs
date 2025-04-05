#!/usr/bin/env node
import { execSync } from 'child_process';
import WebSocket from 'ws';
import net from 'net';
import fs from 'fs/promises';
import { performance } from 'perf_hooks';

// Configuration
const CONFIG = {
  SERVER_IP: '10.42.0.1',
  PORTS: { tcp: 8080, ws: 8081 },
  TEST_MODES: [
    { type: 'latency', durations: [5, 10, 30], sizes: [64, 1024, 10240] },
    { type: 'throughput', durations: [10, 30], sizes: [102400, 1048576] },
    { type: 'jitter', durations: [30], sizes: [1024] }
  ],
  WARMUP: { iterations: 100, duration: 2000 },
  MONITOR_INTERVAL: 500,
  MAX_LISTENERS: 30,
  COOLDOWN_TIME: 10000,
  TEST_RUNS: 10
};

// Get System Specs
async function getSystemSpecs() {
  try {
    return {
      cpu: {
        model: execSync('cat /proc/cpuinfo | grep "Model"', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() || 'Unknown',
        cores: execSync('nproc', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() || 'Unknown',
        freq: execSync('vcgencmd get_config arm_freq || echo "Unknown"', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
      },
      memory: execSync('free -h', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().split('\n')[1] || 'Unknown',
      os: execSync('cat /etc/os-release | grep PRETTY_NAME', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() || 'Unknown',
      network: execSync('iwconfig wlan0 | grep "Bit Rate" || echo "Unknown"', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
    };
  } catch (err) {
    console.error('Error getting system specs:', err);
    return {
      cpu: { model: 'Error', cores: 'Error', freq: 'Error' },
      memory: 'Error',
      os: 'Error',
      network: 'Error'
    };
  }
}

// Analyze monitor data
function analyzeMonitorData(monitorData) {
  const avg = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;

  return {
    cpuAvg: avg(monitorData.cpu),
    memAvg: avg(monitorData.mem),
    tempAvg: avg(monitorData.temp),
    rxTotal: monitorData.net.rx.reduce((sum, x) => sum + (x.bytes || 0), 0),
    txTotal: monitorData.net.tx.reduce((sum, x) => sum + (x.bytes || 0), 0),
    clockAvg: avg(monitorData.clock)
  };
}

// Monitoring system stats
function startMonitoring() {
  let monitorData = {
    timestamps: [],
    cpu: [], mem: [], temp: [],
    net: { rx: [], tx: [] },
    clock: []
  };

  const monitorInterval = setInterval(() => {
    const timestamp = Date.now();
    monitorData.timestamps.push(timestamp);

    try {
      const cpuMem = execSync(
        "top -bn1 | awk '/Cpu\\(s\\):/ {printf \"%.1f\", 100-$8}' && " +
        "free | awk '/Mem:/ {printf \" %.1f\", $3/$2*100}'",
        { stdio: ['ignore', 'pipe', 'ignore'] }
      ).toString().split(' ').map(parseFloat);

      monitorData.cpu.push(cpuMem[0] || 0);
      monitorData.mem.push(cpuMem[1] || 0);
    } catch (err) {
      monitorData.cpu.push(0);
      monitorData.mem.push(0);
    }

    try {
      const tempThrottle = execSync(
        "vcgencmd measure_temp | cut -d= -f2 | cut -d\"'\" -f1 && " +
        "vcgencmd get_throttled",
        { stdio: ['ignore', 'pipe', 'ignore'] }
      ).toString().split('\n');

      monitorData.temp.push(parseFloat(tempThrottle[0]) || 0);
      monitorData.clock.push(
        parseInt(execSync('vcgencmd measure_clock arm', { stdio: ['ignore', 'pipe', 'ignore'] })
          .toString().split('=')[1] || 0)
      );
    } catch {
      monitorData.temp.push(0);
      monitorData.clock.push(0);
    }

    try {
      const netStats = execSync(
        "cat /proc/net/dev | grep wlan0 | awk '{print $2,$3,$10,$11}'",
        { stdio: ['ignore', 'pipe', 'ignore'] }
      ).toString().split(/\s+/).filter(Boolean).map(Number);

      if (netStats.length >= 4) {
        monitorData.net.rx.push({ bytes: netStats[0], packets: netStats[1] });
        monitorData.net.tx.push({ bytes: netStats[2], packets: netStats[3] });
      } else {
        throw new Error('Invalid network stats format');
      }
    } catch {
      monitorData.net.rx.push({ bytes: 0, packets: 0 });
      monitorData.net.tx.push({ bytes: 0, packets: 0 });
    }
  }, CONFIG.MONITOR_INTERVAL);

  return {
    monitorData,
    stopMonitoring: () => clearInterval(monitorInterval),
  };
}

// Warm-up period before starting actual tests
async function warmUp() {
  console.log(`Starting warm-up for ${CONFIG.WARMUP.iterations} iterations, each lasting ${CONFIG.WARMUP.duration / 1000} seconds.`);
  const warmUpStart = performance.now();

  for (let i = 0; i < CONFIG.WARMUP.iterations; i++) {
    const iterationStart = performance.now();
    await new Promise(resolve => setTimeout(resolve, CONFIG.WARMUP.duration));
    const iterationEnd = performance.now();
    console.log(`Warm-up iteration ${i + 1} completed in ${(iterationEnd - iterationStart).toFixed(2)} ms`);
  }

  const warmUpEnd = performance.now();
  console.log(`Warm-up completed in ${(warmUpEnd - warmUpStart).toFixed(2)} ms.`);
}

// Save results
async function saveResults(results, testNumber) {
  const resultFile = `test-${testNumber}.json`;
  await fs.writeFile(resultFile, JSON.stringify(results, null, 2));
  console.log(`Results saved to ${resultFile}`);
}

// Latency iteration
async function latencyIteration(params, sock) {
  const startTime = performance.now();
  return new Promise((resolve, reject) => {
    sock.write(Buffer.alloc(params.messageSize), err => {
      if (err) return reject(err);
      sock.once('data', () => {
        resolve(performance.now() - startTime);
      });
    });
  });
}

// Throughput iteration
async function throughputIteration(params, sock) {
  let bytesSent = 0;
  const buffer = Buffer.alloc(params.messageSize);
  for (let i = 0; i < 1000; i++) {
    sock.write(buffer);
    bytesSent += buffer.length;
  }
  return bytesSent;
}

// Run test
async function runTest(params, monitorData) {
  const sock = new net.Socket();
  const testData = {
    timestamps: [],
    latencies: [],
    throughputs: []
  };

  try {
    sock.connect(CONFIG.PORTS.tcp, CONFIG.SERVER_IP);
    const startTime = performance.now();

    while ((performance.now() - startTime) < params.durationSec * 1000) {
      const iterStart = performance.now();

      if (params.type === 'throughput') {
        const bytesSent = await throughputIteration(params, sock);
        testData.throughputs.push(bytesSent / ((performance.now() - iterStart) / 1000));
      } else {
        const latency = await latencyIteration(params, sock);
        testData.latencies.push(latency);
      }

      testData.timestamps.push(performance.now());
    }

    return {
      ...params,
      metrics: analyzeMonitorData(monitorData),
      timestamp: new Date().toISOString(),
      testData
    };
  } catch (err) {
    console.error(`Test ${params.type}_${params.messageSize}_${params.durationSec} failed:`, err);
    throw err;
  } finally {
    sock.destroy();
  }
}

// Run all tests
async function runAllTests() {
  const results = {
    system: await getSystemSpecs(),
    tests: []
  };

  const { monitorData, stopMonitoring } = startMonitoring();

  try {
    await warmUp();

    for (let testRun = 1; testRun <= CONFIG.TEST_RUNS; testRun++) {
      console.log(`Running test iteration ${testRun}...`);

      if (testRun > 1) {
        console.log(`Cooldown time: ${CONFIG.COOLDOWN_TIME / 1000} seconds...`);
        await new Promise(resolve => setTimeout(resolve, CONFIG.COOLDOWN_TIME));
      }

      for (const mode of CONFIG.TEST_MODES) {
        for (const duration of mode.durations) {
          for (const size of mode.sizes) {
            const params = { type: mode.type, durationSec: duration, messageSize: size };
            console.log(`Running test: ${params.type}_${params.messageSize}_${params.durationSec}`);
            const result = await runTest(params, monitorData);
            results.tests.push(result);
          }
        }
      }

      await saveResults(results, testRun);
    }
  } catch (err) {
    console.error('Error running tests:', err);
  } finally {
    stopMonitoring();
    console.log('All tests completed!');
  }
}

runAllTests().catch(err => console.error('Error:', err));
