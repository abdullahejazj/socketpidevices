#!/bin/bash
set -e

# Configuration
RESULTS_DIR="./results"
mkdir -p "$RESULTS_DIR"
RUNS=10
SYSINFO_FILE="$RESULTS_DIR/system_info.txt"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# System Information Collection
collect_system_info() {
    echo "=== Raspberry Pi 4 Benchmark - $TIMESTAMP ===" > "$SYSINFO_FILE"
    echo -e "\n[System Information]" >> "$SYSINFO_FILE"
    cat /etc/os-release >> "$SYSINFO_FILE"
    echo -e "\nCPU: $(cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d':' -f2 | xargs)" >> "$SYSINFO_FILE"
    echo "Cores: $(nproc)" >> "$SYSINFO_FILE"
    echo "Architecture: $(uname -m)" >> "$SYSINFO_FILE"
    echo "Kernel: $(uname -r)" >> "$SYSINFO_FILE"
    
    echo -e "\n[Memory Information]" >> "$SYSINFO_FILE"
    free -h >> "$SYSINFO_FILE"
    echo -e "\nSwap:" >> "$SYSINFO_FILE"
    swapon --show >> "$SYSINFO_FILE"
    
    echo -e "\n[Disk Information]" >> "$SYSINFO_FILE"
    df -h >> "$SYSINFO_FILE"
    
    echo -e "\n[Temperature]" >> "$SYSINFO_FILE"
    vcgencmd measure_temp >> "$SYSINFO_FILE"
    
    echo -e "\n[Clock Speeds]" >> "$SYSINFO_FILE"
    for i in {0..3}; do
        echo "CPU$i: $(vcgencmd measure_clock arm | cut -d'=' -f2) Hz" >> "$SYSINFO_FILE"
    done
    
    echo -e "\n[Voltages]" >> "$SYSINFO_FILE"
    vcgencmd measure_volts >> "$SYSINFO_FILE"
    
    echo -e "\n[Throttling Status]" >> "$SYSINFO_FILE"
    vcgencmd get_throttled >> "$SYSINFO_FILE"
}

# Performance monitoring during tests
monitor_performance() {
    local test_name=$1
    local monitor_file="$RESULTS_DIR/${test_name}_monitor.log"
    
    echo -e "\n[Performance During $test_name Test]" >> "$SYSINFO_FILE"
    echo "Timestamp,CPU(%),Memory(%),Temp(°C),Throttled" > "$monitor_file"
    
    while true; do
        local timestamp=$(date +"%H:%M:%S")
        local cpu=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
        local mem=$(free -m | awk 'NR==2{printf "%.2f", $3*100/$2 }')
        local temp=$(vcgencmd measure_temp | cut -d'=' -f2 | cut -d"'" -f1)
        local throttled=$(vcgencmd get_throttled | cut -d'=' -f2)
        
        echo "$timestamp,$cpu,$mem,$temp,$throttled" >> "$monitor_file"
        sleep 1
    done
}

# Cleanup function
cleanup() {
    echo "Cleaning up..."
    pkill -f "node http_server.js" || true
    pkill -f "python3 http_server.py" || true
    pkill -f "node socket_server.js" || true
    pkill -f "python3 socket_server.py" || true
    pkill -f "monitor_performance" || true
    rm -rf py_files node_files
    sync
}

# Benchmark logging
log_run() {
    local cmd="$1"
    local test_name="$2"
    local monitor_pid
    
    # Start performance monitoring
    monitor_performance "$test_name" &
    monitor_pid=$!
    
    for ((i=1; i<=RUNS; i++)); do
        echo "---- Run $i ----" | tee -a "$RESULTS_DIR/${test_name}.txt"
        
        # Set CPU performance governor
        echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
        
        # Run test with timing
        start_time=$(date +%s.%N)
        $cmd 2>&1 | tee -a "$RESULTS_DIR/${test_name}.txt"
        exit_code=${PIPESTATUS[0]}
        end_time=$(date +%s.%N)
        duration=$(echo "$end_time - $start_time" | bc)
        
        # Record results
        echo "Run $i: $duration seconds (Exit: $exit_code)" >> "$RESULTS_DIR/${test_name}_summary.txt"
        echo ""
    done
    
    # Stop monitoring
    kill $monitor_pid || true
    
    # Reset CPU governor
    echo "ondemand" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
}

# Main execution
trap cleanup EXIT

# Collect initial system info
collect_system_info

# --------------------------
# CPU-Bound Tests
# --------------------------
echo "Running CPU-Bound Tests..."
log_run "node cpu/fib.js" "cpu_fib_node"
log_run "python3 cpu/fib.py" "cpu_fib_python"
log_run "node cpu/pi.js" "cpu_pi_node"
log_run "python3 cpu/pi.py" "cpu_pi_python"

# --------------------------
# I/O-Bound Tests
# --------------------------
echo "Running I/O-Bound Tests..."

# HTTP Server Tests
for ((i=1; i<=RUNS; i++)); do
    echo "---- HTTP Node.js Run $i ----" | tee -a "$RESULTS_DIR/io_http_node.txt"
    node io/http_server.js > /dev/null 2>&1 &
    SERVER_PID=$!
    monitor_performance "io_http_node" &
    MONITOR_PID=$!
    sleep 5
    
    if command -v wrk &> /dev/null; then
        wrk -t4 -c100 -d10s http://localhost:3000 2>&1 | tee -a "$RESULTS_DIR/io_http_node.txt"
    else
        echo "wrk not installed, skipping HTTP benchmark" | tee -a "$RESULTS_DIR/io_http_node.txt"
    fi
    
    kill $SERVER_PID $MONITOR_PID || true
    sleep 1
done

for ((i=1; i<=RUNS; i++)); do
    echo "---- HTTP Python Run $i ----" | tee -a "$RESULTS_DIR/io_http_python.txt"
    python3 io/http_server.py > /dev/null 2>&1 &
    SERVER_PID=$!
    monitor_performance "io_http_python" &
    MONITOR_PID=$!
    sleep 10
    
    if command -v wrk &> /dev/null; then
        wrk -t4 -c100 -d10s http://localhost:5000 2>&1 | tee -a "$RESULTS_DIR/io_http_python.txt"
    else
        echo "wrk not installed, skipping HTTP benchmark" | tee -a "$RESULTS_DIR/io_http_python.txt"
    fi
    
    kill $SERVER_PID $MONITOR_PID || true
    sleep 1
done

# File I/O Tests
log_run "node io/file_io.js" "io_file_node"
log_run "python3 io/file_io.py" "io_file_python"

# --------------------------
# Memory Tests
# --------------------------
echo "Running Memory Tests..."
log_run "python3 memory/array_py.py" "memory_array_python"
log_run "node memory/array_js.js" "memory_array_node"

# --------------------------
# Socket Tests
# --------------------------
echo "Running Socket Tests..."
for ((i=1; i<=RUNS; i++)); do
    echo "---- Socket Node.js Run $i ----" | tee -a "$RESULTS_DIR/sockets_node.txt"
    node sockets/socket_server.js > /dev/null 2>&1 &
    SERVER_PID=$!
    monitor_performance "sockets_node" &
    MONITOR_PID=$!
    sleep 3
    
    if nc -z localhost 3001; then
        python sockets/socket_client.py "node" 2>&1 | tee -a "$RESULTS_DIR/sockets_node.txt"
    else
        echo "Node.js socket server failed to start" | tee -a "$RESULTS_DIR/sockets_node.txt"
    fi
    
    kill $SERVER_PID $MONITOR_PID || true
    sleep 1
done

for ((i=1; i<=RUNS; i++)); do
    echo "---- Socket Python Run $i ----" | tee -a "$RESULTS_DIR/sockets_python.txt"
    python sockets/socket_server.py > /dev/null 2>&1 &
    SERVER_PID=$!
    monitor_performance "sockets_python" &
    MONITOR_PID=$!
    sleep 10
    
    if nc -z localhost 5001; then
        python sockets/socket_client.py "python" 2>&1 | tee -a "$RESULTS_DIR/sockets_python.txt"
    else
        echo "Python socket server failed to start" | tee -a "$RESULTS_DIR/sockets_python.txt"
    fi
    
    kill $SERVER_PID $MONITOR_PID || true
    sleep 1
done

# Generate final report
echo "Generating final report..."
{
    echo -e "\n=== Benchmark Summary ==="
    echo -e "\nCPU Performance:"
    grep "Run .* seconds" "$RESULTS_DIR"/cpu_*_summary.txt | sort
    echo -e "\nI/O Performance:"
    grep "Requests/sec" "$RESULTS_DIR"/io_http_*.txt || echo "No HTTP results"
    grep "Time:" "$RESULTS_DIR"/io_file_*.txt || echo "No File I/O results"
    echo -e "\nMemory Performance:"
    grep "Time:" "$RESULTS_DIR"/memory_*.txt
    echo -e "\nSocket Performance:"
    grep "Avg Latency" "$RESULTS_DIR"/sockets_*.txt
} > "$RESULTS_DIR/benchmark_summary_$TIMESTAMP.txt"

echo "✅ Benchmark completed! Results saved to $RESULTS_DIR"
echo "System information: $SYSINFO_FILE"
echo "Performance summary: $RESULTS_DIR/benchmark_summary_$TIMESTAMP.txt"