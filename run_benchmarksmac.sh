#!/bin/bash
set -e

RESULTS_DIR="./results"
mkdir -p "$RESULTS_DIR"
RUNS=10
SYSINFO_FILE="$RESULTS_DIR/system_info.txt"

# System Information Collection
collect_system_info() {
    echo "=== System Information ===" > "$SYSINFO_FILE"
    echo "Timestamp: $(date)" >> "$SYSINFO_FILE"
    echo -e "\n[OS Information]" >> "$SYSINFO_FILE"
    cat /etc/os-release >> "$SYSINFO_FILE"
    
    echo -e "\n[Hardware Information]" >> "$SYSINFO_FILE"
    echo "CPU: $(cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d':' -f2 | xargs)" >> "$SYSINFO_FILE"
    echo "Cores: $(nproc)" >> "$SYSINFO_FILE"
    echo "Architecture: $(uname -m)" >> "$SYSINFO_FILE"
    echo "Kernel: $(uname -r)" >> "$SYSINFO_FILE"
    
    echo -e "\n[Memory Information]" >> "$SYSINFO_FILE"
    free -h >> "$SYSINFO_FILE"
    
    echo -e "\n[Disk Information]" >> "$SYSINFO_FILE"
    df -h >> "$SYSINFO_FILE"
    
    echo -e "\n[Raspberry Pi Specific]" >> "$SYSINFO_FILE"
    if command -v vcgencmd &> /dev/null; then
        echo "Temperature: $(vcgencmd measure_temp)" >> "$SYSINFO_FILE"
        echo "Clock speed: $(vcgencmd measure_clock arm)" >> "$SYSINFO_FILE"
        echo "Voltage: $(vcgencmd measure_volts)" >> "$SYSINFO_FILE"
        echo "Throttle status: $(vcgencmd get_throttled)" >> "$SYSINFO_FILE"
    fi
}

# Use gtime if available (from brew install gnu-time)
if command -v gtime &> /dev/null; then
    TIME_CMD="gtime -v"
elif command -v /usr/bin/time &> /dev/null; then
    TIME_CMD="/usr/bin/time -l"
else
    TIME_CMD=""
fi

cleanup() {
    echo "Cleaning up..."
    pkill -f "node http_server.js" || true
    pkill -f "python3 http_server.py" || true
    pkill -f "node socket_server.js" || true
    pkill -f "python3 socket_server.py" || true
    rm -rf py_files node_files
}
trap cleanup EXIT

log_run() {
    local cmd="$1"
    local output_file="$2"

    for ((i=1; i<=RUNS; i++)); do
        echo "---- Run $i ----" | tee -a "$output_file"
        if [ -n "$TIME_CMD" ]; then
            $TIME_CMD $cmd 2>&1 | tee -a "$output_file"
        else
            $cmd 2>&1 | tee -a "$output_file"
        fi
        echo "" | tee -a "$output_file"
    done
}

# Collect system info first
collect_system_info

# --------------------------
# CPU-Bound Tests
# --------------------------
echo "CPU-Bound Tests..."
log_run "node cpu/fib.js" "$RESULTS_DIR/cpu_fib_node.txt"
log_run "python3 cpu/fib.py" "$RESULTS_DIR/cpu_fib_python.txt"
log_run "node cpu/pi.js" "$RESULTS_DIR/cpu_pi_node.txt"
log_run "python3 cpu/pi.py" "$RESULTS_DIR/cpu_pi_python.txt"

# --------------------------
# I/O-Bound Tests
# --------------------------
echo "I/O-Bound Tests..."
for ((i=1; i<=RUNS; i++)); do
    echo "---- Run $i ----" | tee -a "$RESULTS_DIR/io_http_node.txt"
    node io/http_server.js > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 5
    if command -v wrk &> /dev/null; then
        wrk -t4 -c100 -d10s http://localhost:3000 2>&1 | tee -a "$RESULTS_DIR/io_http_node.txt"
    else
        echo "wrk not installed, skipping HTTP benchmark" | tee -a "$RESULTS_DIR/io_http_node.txt"
    fi
    kill $SERVER_PID || true
    sleep 1
done

for ((i=1; i<=RUNS; i++)); do
    echo "---- Run $i ----" | tee -a "$RESULTS_DIR/io_http_python.txt"
    python3 io/http_server.py > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 10
    if command -v wrk &> /dev/null; then
        wrk -t4 -c100 -d10s http://localhost:5000 2>&1 | tee -a "$RESULTS_DIR/io_http_python.txt"
    else
        echo "wrk not installed, skipping HTTP benchmark" | tee -a "$RESULTS_DIR/io_http_python.txt"
    fi
    kill $SERVER_PID || true
    sleep 1
done

log_run "node io/file_io.js" "$RESULTS_DIR/io_file_node.txt"
log_run "python3 io/file_io.py" "$RESULTS_DIR/io_file_python.txt"

# --------------------------
# Memory Tests
# --------------------------
echo "Memory Tests..."
log_run "python3 memory/array_py.py" "$RESULTS_DIR/memory_array_python.txt"
log_run "node memory/array_js.js" "$RESULTS_DIR/memory_array_node.txt"

# --------------------------
# Socket Tests
# --------------------------
echo "Socket Tests..."
for ((i=1; i<=RUNS; i++)); do
    echo "---- Run $i ----" | tee -a "$RESULTS_DIR/sockets_node.txt"
    node sockets/socket_server.js > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 3
    if nc -z localhost 3001; then
        python sockets/socket_client.py "node" 2>&1 | tee -a "$RESULTS_DIR/sockets_node.txt"
    else
        echo "Node.js socket server failed to start" | tee -a "$RESULTS_DIR/sockets_node.txt"
    fi
    kill $SERVER_PID || true
    sleep 1
done

for ((i=1; i<=RUNS; i++)); do
    echo "---- Run $i ----" | tee -a "$RESULTS_DIR/sockets_python.txt"
    python sockets/socket_server.py > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 10
    if nc -z localhost 5001; then
        python sockets/socket_client.py "python" 2>&1 | tee -a "$RESULTS_DIR/sockets_python.txt"
    else
        echo "Python socket server failed to start" | tee -a "$RESULTS_DIR/sockets_python.txt"
    fi
    kill $SERVER_PID || true
    sleep 1
done

echo "✅ Benchmark completed! Results saved to $RESULTS_DIR"
echo "System information saved to $SYSINFO_FILE"