import asyncio
import json
import socket
import subprocess
import threading
import time
from datetime import datetime

# Configuration - matches Node.js version exactly
CONFIG = {
    'SERVER_IP': '10.42.0.1',
    'PORTS': {'tcp': 8080, 'ws': 8081},
    'TEST_MODES': [
        {'type': 'latency', 'durations': [5, 10, 30], 'sizes': [64, 1024, 10240]},
        {'type': 'throughput', 'durations': [10, 30], 'sizes': [102400, 1048576]},
        {'type': 'jitter', 'durations': [30], 'sizes': [1024]}
    ],
    'WARMUP': {'iterations': 100, 'duration': 2000},
    'MONITOR_INTERVAL': 500,
    'MAX_LISTENERS': 30,
    'COOLDOWN_TIME': 10000,
    'TEST_RUNS': 10
}

def get_system_specs():
    try:
        return {
            'cpu': {
                'model': subprocess.check_output('cat /proc/cpuinfo | grep "Model"', shell=True).decode().strip() or 'Unknown',
                'cores': subprocess.check_output('nproc', shell=True).decode().strip() or 'Unknown',
                'freq': subprocess.check_output('vcgencmd get_config arm_freq || echo "Unknown"', shell=True).decode().strip()
            },
            'memory': subprocess.check_output('free -h', shell=True).decode().split('\n')[1] or 'Unknown',
            'os': subprocess.check_output('cat /etc/os-release | grep PRETTY_NAME', shell=True).decode().strip() or 'Unknown',
            'network': subprocess.check_output('iwconfig wlan0 | grep "Bit Rate" || echo "Unknown"', shell=True).decode().strip()
        }
    except Exception as err:
        print('Error getting system specs:', err)
        return {
            'cpu': {'model': 'Error', 'cores': 'Error', 'freq': 'Error'},
            'memory': 'Error',
            'os': 'Error',
            'network': 'Error'
        }

def analyze_monitor_data(monitor_data):
    def avg(arr):
        return sum(arr) / len(arr) if arr else 0
    
    return {
        'cpuAvg': avg(monitor_data['cpu']),
        'memAvg': avg(monitor_data['mem']),
        'tempAvg': avg(monitor_data['temp']),
        'rxTotal': sum(x['bytes'] for x in monitor_data['net']['rx']),
        'txTotal': sum(x['bytes'] for x in monitor_data['net']['tx']),
        'clockAvg': avg(monitor_data['clock'])
    }

def start_monitoring():
    monitor_data = {
        'timestamps': [],
        'cpu': [], 'mem': [], 'temp': [],
        'net': {'rx': [], 'tx': []},
        'clock': []
    }
    
    stop_event = threading.Event()
    
    def monitor_loop():
        while not stop_event.is_set():
            timestamp = time.time() * 1000  # milliseconds
            monitor_data['timestamps'].append(timestamp)
            
            try:
                cpu_mem = subprocess.check_output(
                    "top -bn1 | awk '/Cpu\\(s\\):/ {printf \"%.1f\", 100-$8}' && "
                    "free | awk '/Mem:/ {printf \" %.1f\", $3/$2*100}'",
                    shell=True
                ).decode().split()
                monitor_data['cpu'].append(float(cpu_mem[0]) if cpu_mem else 0)
                monitor_data['mem'].append(float(cpu_mem[1]) if len(cpu_mem) > 1 else 0)
            except:
                monitor_data['cpu'].append(0)
                monitor_data['mem'].append(0)
            
            try:
                temp_throttle = subprocess.check_output(
                    "vcgencmd measure_temp | cut -d= -f2 | cut -d\"'\" -f1 && "
                    "vcgencmd get_throttled",
                    shell=True
                ).decode().split('\n')
                monitor_data['temp'].append(float(temp_throttle[0]) if temp_throttle else 0)
                
                clock = subprocess.check_output(
                    'vcgencmd measure_clock arm',
                    shell=True
                ).decode().split('=')
                monitor_data['clock'].append(int(clock[1]) if len(clock) > 1 else 0)
            except:
                monitor_data['temp'].append(0)
                monitor_data['clock'].append(0)
            
            try:
                net_stats = subprocess.check_output(
                    "cat /proc/net/dev | grep wlan0 | awk '{print $2,$3,$10,$11}'",
                    shell=True
                ).decode().split()
                if len(net_stats) >= 4:
                    monitor_data['net']['rx'].append({
                        'bytes': int(net_stats[0]),
                        'packets': int(net_stats[1])
                    })
                    monitor_data['net']['tx'].append({
                        'bytes': int(net_stats[2]),
                        'packets': int(net_stats[3])
                    })
                else:
                    raise ValueError('Invalid network stats format')
            except:
                monitor_data['net']['rx'].append({'bytes': 0, 'packets': 0})
                monitor_data['net']['tx'].append({'bytes': 0, 'packets': 0})
            
            time.sleep(CONFIG['MONITOR_INTERVAL'] / 1000)
    
    monitor_thread = threading.Thread(target=monitor_loop)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    return {
        'monitor_data': monitor_data,
        'stop_monitoring': lambda: stop_event.set()
    }

async def warm_up():
    print(f"Starting warm-up for {CONFIG['WARMUP']['iterations']} iterations, "
          f"each lasting {CONFIG['WARMUP']['duration'] / 1000} seconds.")
    warm_up_start = time.perf_counter()
    
    for i in range(CONFIG['WARMUP']['iterations']):
        iteration_start = time.perf_counter()
        await asyncio.sleep(CONFIG['WARMUP']['duration'] / 1000)
        iteration_end = time.perf_counter()
        print(f"Warm-up iteration {i + 1} completed in {(iteration_end - iteration_start) * 1000:.2f} ms")
    
    warm_up_end = time.perf_counter()
    print(f"Warm-up completed in {(warm_up_end - warm_up_start) * 1000:.2f} ms.")

async def save_results(results, test_number):
    result_file = f'test-{test_number}.json'
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {result_file}")

def latency_iteration(params, sock):
    start_time = time.perf_counter()
    sock.send(bytes(params['messageSize']))
    sock.recv(params['messageSize'])
    return (time.perf_counter() - start_time) * 1000  # convert to milliseconds

def throughput_iteration(params, sock):
    bytes_sent = 0
    buffer = bytes(params['messageSize'])
    for _ in range(1000):
        sock.send(buffer)
        bytes_sent += len(buffer)
    return bytes_sent

async def run_test(params, monitor_data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_data = {
        'timestamps': [],
        'latencies': [],
        'throughputs': []
    }
    
    try:
        sock.connect((CONFIG['SERVER_IP'], CONFIG['PORTS']['tcp']))
        start_time = time.perf_counter()
        
        while (time.perf_counter() - start_time) < params['durationSec']:
            iter_start = time.perf_counter()
            
            if params['type'] == 'throughput':
                bytes_sent = throughput_iteration(params, sock)
                test_data['throughputs'].append(bytes_sent / ((time.perf_counter() - iter_start) / 1000))
            else:
                latency = latency_iteration(params, sock)
                test_data['latencies'].append(latency)
            
            test_data['timestamps'].append(time.perf_counter() * 1000)  # milliseconds
            
        return {
            **params,
            'metrics': analyze_monitor_data(monitor_data),
            'timestamp': datetime.now().isoformat(),
            'test_data': test_data
        }
    except Exception as err:
        print(f"Test {params['type']}_{params['messageSize']}_{params['durationSec']} failed:", err)
        raise err
    finally:
        sock.close()

async def run_all_tests():
    results = {
        'system': get_system_specs(),
        'tests': []
    }
    
    monitor = start_monitoring()
    
    try:
        await warm_up()
        
        for test_run in range(1, CONFIG['TEST_RUNS'] + 1):
            print(f"Running test iteration {test_run}...")
            
            if test_run > 1:
                print(f"Cooldown time: {CONFIG['COOLDOWN_TIME'] / 1000} seconds...")
                await asyncio.sleep(CONFIG['COOLDOWN_TIME'] / 1000)
            
            for mode in CONFIG['TEST_MODES']:
                for duration in mode['durations']:
                    for size in mode['sizes']:
                        params = {
                            'type': mode['type'],
                            'durationSec': duration,
                            'messageSize': size
                        }
                        print(f"Running test: {params['type']}_{params['messageSize']}_{params['durationSec']}")
                        result = await run_test(params, monitor['monitor_data'])
                        results['tests'].append(result)
            
            await save_results(results, test_run)
    except Exception as err:
        print("Error running tests:", err)
    finally:
        monitor['stop_monitoring']()
        print("All tests completed!")

if __name__ == '__main__':
    asyncio.run(run_all_tests())