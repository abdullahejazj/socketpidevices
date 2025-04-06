#!/usr/bin/env python3
import asyncio
import subprocess
import socket
import json
import time
from time import perf_counter
from threading import Thread, Event
from datetime import datetime

# Configuration (matches Node.js version)
CONFIG = {
    "SERVER_IP": "10.42.0.1",
    "PORTS": {"tcp": 8080, "ws": 8081},
    "TEST_MODES": [
        # {"type": "latency", "durations": [5, 10, 30], "sizes": [64, 1024, 10240]},
        {"type": "throughput", "durations": [10, 30], "sizes": [102400, 1048576]},
        # {"type": "jitter", "durations": [30], "sizes": [1024]}
    ],
    "WARMUP": {"iterations": 1, "duration": 2000},
    "MONITOR_INTERVAL": 500,
    "MAX_LISTENERS": 30,
    "COOLDOWN_TIME": 10000,
    "TEST_RUNS": 10
}

def apply_system_optimizations():
    """Apply recommended system optimizations for Raspberry Pi"""
    try:
        # Increase TCP buffer sizes
        subprocess.run(["sudo", "sysctl", "-w", "net.core.rmem_max=16777216"], check=True)
        subprocess.run(["sudo", "sysctl", "-w", "net.core.wmem_max=16777216"], check=True)
        subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.tcp_rmem='4096 87380 16777216'"], check=True)
        subprocess.run(["sudo", "sysctl", "-w", "net.ipv4.tcp_wmem='4096 16384 16777216'"], check=True)
        
        # Increase connection backlog
        subprocess.run(["sudo", "sysctl", "-w", "net.core.somaxconn=65535"], check=True)
        
        # Raspberry Pi specific optimizations
        subprocess.run(["sudo", "sysctl", "-w", "vm.swappiness=10"], check=True)
        subprocess.run(["sudo", "sysctl", "-w", "vm.vfs_cache_pressure=50"], check=True)
        
        print("Applied Raspberry Pi optimizations")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not apply all optimizations: {e}")

async def get_system_specs():
    """Get Raspberry Pi system specs matching Node.js format"""
    try:
        cpu_model = subprocess.check_output(
            'cat /proc/cpuinfo | grep "Model"', shell=True, stderr=subprocess.DEVNULL
        ).decode().strip() or "Unknown"
    except Exception:
        cpu_model = "Unknown"
    
    try:
        cores = subprocess.check_output("nproc", shell=True, stderr=subprocess.DEVNULL
        ).decode().strip() or "Unknown"
    except Exception:
        cores = "Unknown"
    
    try:
        freq = subprocess.check_output(
            'vcgencmd get_config arm_freq || echo "Unknown"', shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        freq = "Unknown"
    
    try:
        memory = subprocess.check_output("free -h", shell=True, stderr=subprocess.DEVNULL
        ).decode().split("\n")[1].strip()
    except Exception:
        memory = "Unknown"
    
    try:
        os_info = subprocess.check_output(
            'cat /etc/os-release | grep PRETTY_NAME', shell=True, stderr=subprocess.DEVNULL
        ).decode().strip().strip('"').split('=')[1] or "Unknown"
    except Exception:
        os_info = "Unknown"
    
    try:
        network = subprocess.check_output(
            'iwconfig wlan0 | grep "Bit Rate" || echo "Unknown"', shell=True, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        network = "Unknown"

    return {
        "cpu": {"model": cpu_model, "cores": cores, "freq": freq},
        "memory": memory,
        "os": os_info,
        "network": network
    }

def analyze_monitor_data(monitor_data):
    """Analyze monitor data to match Node.js format"""
    def avg(arr):
        return sum(arr) / len(arr) if arr else 0

    return {
        "cpuAvg": avg(monitor_data["cpu"]),
        "memAvg": avg(monitor_data["mem"]),
        "tempAvg": avg(monitor_data["temp"]),
        "rxTotal": sum(x["bytes"] for x in monitor_data["net"]["rx"]),
        "txTotal": sum(x["bytes"] for x in monitor_data["net"]["tx"]),
        "clockAvg": avg(monitor_data["clock"])
    }

def start_monitoring():
    """System monitoring for Raspberry Pi"""
    monitor_data = {
        "timestamps": [],
        "cpu": [],
        "mem": [],
        "temp": [],
        "net": {"rx": [], "tx": []},
        "clock": []
    }
    stop_event = Event()

    def monitor_loop():
        while not stop_event.is_set():
            try:
                # Timestamp
                timestamp = int(time.time() * 1000)
                monitor_data["timestamps"].append(timestamp)

                # CPU and Memory (Raspberry Pi compatible)
                cmd = 'top -bn1 | awk \'/Cpu\\(s\\):/ {printf "%.1f", 100-$8}\' && free | awk \'/Mem:/ {printf " %.1f", $3/$2*100}\''
                output = subprocess.check_output(cmd, shell=True).decode().split()
                monitor_data["cpu"].append(float(output[0]))
                monitor_data["mem"].append(float(output[1]))
                
                # Temperature (Raspberry Pi specific)
                temp = float(subprocess.check_output(
                    'vcgencmd measure_temp | cut -d= -f2 | cut -d\'\\\'\' -f1',
                    shell=True
                ).decode().strip())
                monitor_data["temp"].append(temp)
                
                # Clock (Raspberry Pi specific)
                clock = int(subprocess.check_output(
                    'vcgencmd measure_clock arm',
                    shell=True
                ).decode().split('=')[1].strip())
                monitor_data["clock"].append(clock)
                
                # Network (Raspberry Pi compatible)
                net_stats = subprocess.check_output(
                    "cat /proc/net/dev | grep -E 'wlan0|eth0' | awk '{print $2,$3,$10,$11}'",
                    shell=True
                ).decode().split()
                if len(net_stats) >= 4:
                    monitor_data["net"]["rx"].append({
                        "bytes": int(net_stats[0]),
                        "packets": int(net_stats[1])
                    })
                    monitor_data["net"]["tx"].append({
                        "bytes": int(net_stats[2]),
                        "packets": int(net_stats[3])
                    })
                else:
                    monitor_data["net"]["rx"].append({"bytes": 0, "packets": 0})
                    monitor_data["net"]["tx"].append({"bytes": 0, "packets": 0})

                time.sleep(CONFIG["MONITOR_INTERVAL"] / 1000)
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(1)

    monitor_thread = Thread(target=monitor_loop)
    monitor_thread.start()

    def stop_monitoring():
        stop_event.set()
        monitor_thread.join()

    return monitor_data, stop_monitoring

async def warm_up():
    """Warm-up period matching Node.js implementation"""
    print(f"Starting warm-up for {CONFIG['WARMUP']['iterations']} iterations")
    warm_up_start = perf_counter()
    
    for i in range(CONFIG["WARMUP"]["iterations"]):
        iter_start = perf_counter()
        await asyncio.sleep(CONFIG["WARMUP"]["duration"] / 1000)
        print(f"Warm-up iteration {i+1} completed in {(perf_counter() - iter_start)*1000:.2f} ms")
    
    print(f"Warm-up completed in {(perf_counter() - warm_up_start)*1000:.2f} ms")

async def save_results(results, test_number):
    """Save results in same format as Node.js"""
    result_file = f"test-{test_number}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {result_file}")

async def latency_iteration(params):
    """Latency test with proper socket handling"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(5.0)
    
    try:
        sock.connect((CONFIG["SERVER_IP"], CONFIG["PORTS"]["tcp"]))
        start_time = perf_counter()
        sock.sendall(bytearray(params["messageSize"]))
        
        # Wait for echo
        received = 0
        while received < params["messageSize"]:
            data = sock.recv(params["messageSize"] - received)
            if not data:
                break
            received += len(data)
        
        return (perf_counter() - start_time) * 1000  # Convert to ms
    except Exception as e:
        print(f"Latency test error: {e}")
        return None
    finally:
        sock.close()

async def throughput_iteration(params):
    """Throughput test matching Node.js implementation"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(10.0)
    
    try:
        sock.connect((CONFIG["SERVER_IP"], CONFIG["PORTS"]["tcp"]))
        buffer = bytearray(params["messageSize"])
        bytes_sent = 0
        start_time = perf_counter()
        
        for _ in range(1000):  # Match Node.js 1000 iterations
            sock.sendall(buffer)
            bytes_sent += len(buffer)
        
        elapsed = perf_counter() - start_time
        return bytes_sent / elapsed if elapsed > 0 else 0
    except Exception as e:
        print(f"Throughput test error: {e}")
        return None
    finally:
        sock.close()

async def run_test(params, monitor_data):
    """Run a single test with proper error handling"""
    test_data = {
        "timestamps": [],
        "latencies": [],
        "throughputs": []
    }
    
    start_time = perf_counter()
    try:
        while (perf_counter() - start_time) < params["durationSec"]:
            iter_time = perf_counter()
            
            if params["type"] == "throughput":
                throughput = await throughput_iteration(params)
                if throughput is not None:
                    test_data["throughputs"].append(throughput)
            else:  # latency or jitter
                latency = await latency_iteration(params)
                if latency is not None:
                    test_data["latencies"].append(latency)
            
            test_data["timestamps"].append(int(perf_counter() * 1000))
    except Exception as e:
        print(f"Test error: {e}")
    
    return {
        **params,
        "metrics": analyze_monitor_data(monitor_data),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "testData": test_data
    }

async def run_all_tests():
    """Main test execution matching Node.js workflow"""
    apply_system_optimizations()
    results = {
        "system": await get_system_specs(),
        "tests": []
    }
    monitor_data, stop_monitoring = start_monitoring()
    
    try:
        await warm_up()
        
        for test_run in range(1, CONFIG["TEST_RUNS"] + 1):
            print(f"\n=== Test Run {test_run}/{CONFIG['TEST_RUNS']} ===")
            
            if test_run > 1:
                print(f"Cooldown for {CONFIG['COOLDOWN_TIME']/1000} seconds...")
                await asyncio.sleep(CONFIG["COOLDOWN_TIME"] / 1000)
            
            for mode in CONFIG["TEST_MODES"]:
                for duration in mode["durations"]:
                    for size in mode["sizes"]:
                        params = {
                            "type": mode["type"],
                            "durationSec": duration,
                            "messageSize": size
                        }
                        print(f"Running {params['type']} test (size={size}, duration={duration}s)")
                        
                        try:
                            result = await run_test(params, monitor_data)
                            if result:
                                results["tests"].append(result)
                        except Exception as e:
                            print(f"Test failed: {e}")
            
            await save_results(results, test_run)
    except KeyboardInterrupt:
        print("\nTests interrupted")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        stop_monitoring()
        print("\nAll tests completed!")

if __name__ == "__main__":
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\nTests interrupted")
    except Exception as e:
        print(f"Fatal error: {e}")