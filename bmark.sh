#!/bin/bash
set -eo pipefail

# Configuration
RESULTS_DIR="./results"
REPORT_FILE="$RESULTS_DIR/benchmark_report.json"
RUNS=10
TIMEOUT_SEC=30

# Ensure results directory exists
mkdir -p "$RESULTS_DIR"

# Initialize JSON report
echo '{
  "metadata": {
    "system": "'$(uname -a)'",
    "date": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'",
    "runs_per_test": '$RUNS'
  },
  "tests": {}
}' > "$REPORT_FILE"

# Function to add test results to report
add_test_result() {
  jq --arg test "$1" \
     --arg lang "$2" \
     --argjson run "$3" \
     --argjson time "$4" \
     --argjson exit_code "$5" \
     --arg output "$6" \
     '.tests[$test][$lang] += [{
       "run": $run,
       "time_sec": $time,
       "exit_code": $exit_code,
       "output": $output
     }]' "$REPORT_FILE" > "$REPORT_FILE.tmp" && mv "$REPORT_FILE.tmp" "$REPORT_FILE"
}

# Function to run a test with timeout
run_with_timeout() {
  local cmd="$1"
  local timeout="$2"
  local start end duration exit_code output
  
  start=$(date +%s.%N)
  output=$(timeout "$timeout" bash -c "$cmd" 2>&1)
  exit_code=$?
  end=$(date +%s.%N)
  
  duration=$(echo "$end - $start" | bc)
  echo "$output"
  return $exit_code
}

# CPU Tests
run_cpu_tests() {
  echo "Running CPU benchmarks..."
  
  # Fibonacci
  for i in $(seq 1 $RUNS); do
    echo "  Fibonacci Run $i/$RUNS"
    
    # Node.js
    output=$(run_with_timeout "node cpu/fib.js" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "cpu_fib" "node" "$i" "${time:-null}" "$?" "$output"
    
    # Python
    output=$(run_with_timeout "python3 cpu/fib.py" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "cpu_fib" "python" "$i" "${time:-null}" "$?" "$output"
  done
  
  # Pi Calculation
  for i in $(seq 1 $RUNS); do
    echo "  Pi Calculation Run $i/$RUNS"
    
    # Node.js
    output=$(run_with_timeout "node cpu/pi.js" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "cpu_pi" "node" "$i" "${time:-null}" "$?" "$output"
    
    # Python
    output=$(run_with_timeout "python3 cpu/pi.py" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "cpu_pi" "python" "$i" "${time:-null}" "$?" "$output"
  done
}

# I/O Tests
run_io_tests() {
  echo "Running I/O benchmarks..."
  
  # Start servers
  node io/http_server.js > "$RESULTS_DIR/node_server.log" 2>&1 &
  NODE_PID=$!
  python3 io/http_server.py > "$RESULTS_DIR/python_server.log" 2>&1 &
  PYTHON_PID=$!
  sleep 5
  
  # HTTP Tests
  for i in $(seq 1 $RUNS); do
    echo "  HTTP Benchmark Run $i/$RUNS"
    
    # Node.js
    output=$(run_with_timeout "wrk -t4 -c100 -d5s http://localhost:3000" $TIMEOUT_SEC)
    req_sec=$(echo "$output" | grep "Requests/sec" | awk '{print $2}')
    add_test_result "io_http" "node" "$i" "${req_sec:-null}" "$?" "$output"
    
    # Python
    output=$(run_with_timeout "wrk -t4 -c100 -d5s http://localhost:5000" $TIMEOUT_SEC)
    req_sec=$(echo "$output" | grep "Requests/sec" | awk '{print $2}')
    add_test_result "io_http" "python" "$i" "${req_sec:-null}" "$?" "$output"
  done
  
  # File I/O Tests
  for i in $(seq 1 $RUNS); do
    echo "  File I/O Run $i/$RUNS"
    
    # Node.js
    output=$(run_with_timeout "node io/file_io.js" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "io_file" "node" "$i" "${time:-null}" "$?" "$output"
    
    # Python
    output=$(run_with_timeout "python3 io/file_io.py" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "io_file" "python" "$i" "${time:-null}" "$?" "$output"
  done
  
  # Cleanup servers
  kill $NODE_PID $PYTHON_PID || true
}

# Memory Tests
run_memory_tests() {
  echo "Running memory benchmarks..."
  
  for i in $(seq 1 $RUNS); do
    echo "  Memory Test Run $i/$RUNS"
    
    # Node.js
    output=$(run_with_timeout "node memory/array_js.js" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "memory" "node" "$i" "${time:-null}" "$?" "$output"
    
    # Python
    output=$(run_with_timeout "python3 memory/array_py.py" $TIMEOUT_SEC)
    time=$(echo "$output" | grep -E "^Time:" | awk '{print $2}')
    add_test_result "memory" "python" "$i" "${time:-null}" "$?" "$output"
  done
}

# Socket Tests
run_socket_tests() {
  echo "Running socket benchmarks..."
  
  # Start servers
  node sockets/socket_server.js > "$RESULTS_DIR/node_socket.log" 2>&1 &
  NODE_SOCKET_PID=$!
  python3 sockets/socket_server.py > "$RESULTS_DIR/python_socket.log" 2>&1 &
  PYTHON_SOCKET_PID=$!
  sleep 5
  
  for i in $(seq 1 $RUNS); do
    echo "  Socket Test Run $i/$RUNS"
    
    # Node.js
    output=$(run_with_timeout "python3 sockets/socket_client.py node" $TIMEOUT_SEC)
    latency=$(echo "$output" | grep "Avg Latency:" | awk '{print $3}')
    add_test_result "socket" "node" "$i" "${latency:-null}" "$?" "$output"
    
    # Python
    output=$(run_with_timeout "python3 sockets/socket_client.py python" $TIMEOUT_SEC)
    latency=$(echo "$output" | grep "Avg Latency:" | awk '{print $3}')
    add_test_result "socket" "python" "$i" "${latency:-null}" "$?" "$output"
  done
  
  # Cleanup servers
  kill $NODE_SOCKET_PID $PYTHON_SOCKET_PID || true
}

# Generate summary statistics
generate_summary() {
  echo "Generating summary report..."
  
  jq '
  def summary_stats:
    if length == 0 then null else
      (map(.time_sec | select(. != null)) | {
        count: length,
        avg: (if length > 0 then (add / length) else null end),
        min: (if length > 0 then min else null end),
        max: (if length > 0 then max else null end),
        success_rate: ((map(select(.exit_code == 0)) | length / length * 100)
      } end;
  
  .summary = {
    cpu_fib: {
      node: (.tests.cpu_fib.node | summary_stats),
      python: (.tests.cpu_fib.python | summary_stats)
    },
    cpu_pi: {
      node: (.tests.cpu_pi.node | summary_stats),
      python: (.tests.cpu_pi.python | summary_stats)
    },
    io_http: {
      node: (.tests.io_http.node | summary_stats),
      python: (.tests.io_http.python | summary_stats)
    },
    io_file: {
      node: (.tests.io_file.node | summary_stats),
      python: (.tests.io_file.python | summary_stats)
    },
    memory: {
      node: (.tests.memory.node | summary_stats),
      python: (.tests.memory.python | summary_stats)
    },
    socket: {
      node: (.tests.socket.node | summary_stats),
      python: (.tests.socket.python | summary_stats)
    }
  }' "$REPORT_FILE" > "$REPORT_FILE.tmp" && mv "$REPORT_FILE.tmp" "$REPORT_FILE"
}

# Print human-readable results
print_results() {
  echo -e "\nBenchmark Results Summary:"
  echo "========================================"
  
  jq -r '
  def format_time(t):
    if t == null then "N/A" else "\(t*1000 | round)ms" end;
  
  def format_rate(r):
    if r == null then "N/A" else "\(r | round) req/s" end;
  
  def format_comparison(node, python):
    if node.avg == null or python.avg == null then "N/A"
    else "\(python.avg/node.avg | round(1))x faster" end;
  
  .summary | to_entries[] | 
  "TEST: \(.key | ascii_upcase)\n" +
  "  Node.js: \(.value.node | 
    if .key | contains("io_http") then format_rate(.avg)
    else format_time(.avg) end) " +
    "(Success: \(.value.node.success_rate // 0 | round)%)\n" +
  "  Python:  \(.value.python | 
    if .key | contains("io_http") then format_rate(.avg)
    else format_time(.avg) end) " +
    "(Success: \(.value.python.success_rate // 0 | round)%)\n" +
  "  Comparison: \(format_comparison(.value.node, .value.python))\n" +
  "----------------------------------------"' "$REPORT_FILE"
  
  echo -e "\nDetailed report saved to: $REPORT_FILE"
}

# Main execution
main() {
  run_cpu_tests
  run_io_tests
  run_memory_tests
  run_socket_tests
  generate_summary
  print_results
}

# Run main function
main