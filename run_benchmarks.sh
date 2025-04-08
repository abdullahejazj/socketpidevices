#!/bin/bash
set -eo pipefail

# Configuration
RESULTS_DIR="./results"
REPORT_FILE="$RESULTS_DIR/benchmark_report.json"
RUNS=2  # Start with 2 runs for testing
TIMEOUT_SEC=30

# Check dependencies
check_dependency() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Error: $1 is required but not installed."
        exit 1
    fi
}

check_dependency "jq"
check_dependency "bc"

# macOS compatibility fixes
get_timestamp() {
    if command -v gdate >/dev/null 2>&1; then
        gdate +%s.%N
    else
        python -c 'import time; print(time.time())'
    fi
}

# Initialize results directory
mkdir -p "$RESULTS_DIR"
echo '{"metadata": {}, "tests": {}}' > "$REPORT_FILE"

# Benchmark functions
run_test() {
    local test_name=$1
    local cmd=$2
    local lang=$3
    
    echo "Running $test_name ($lang)..."
    
    for ((i=1; i<=RUNS; i++)); do
        local start end duration exit_code output
        start=$(get_timestamp)
        output=$(timeout $TIMEOUT_SEC bash -c "$cmd" 2>&1 || true)
        exit_code=$?
        end=$(get_timestamp)
        
        # Calculate duration with bc for floating point
        duration=$(echo "$end - $start" | bc || echo "null")
        
        # Parse numeric metrics
        local metric=$(echo "$output" | awk '
            /Time:/ {print $2}
            /Requests\/sec:/ {print $2}
            /Avg Latency:/ {print $3}
        ' | tr -d 'ms')
        
        jq --arg test "$test_name" \
           --arg lang "$lang" \
           --argjson run "$i" \
           --argjson time "${metric:-null}" \
           --argjson duration "$duration" \
           --argjson exit "$exit_code" \
           '.tests[$test][$lang] += [{
             run: $run,
             metric: $time,
             duration: $duration,
             exit_code: $exit
           }]' "$REPORT_FILE" > tmp.json && mv tmp.json "$REPORT_FILE"
    done
}

# Main tests
main() {
    # CPU Tests
    run_test "cpu_fib" "node cpu/fib.js" "node"
    run_test "cpu_fib" "python3 cpu/fib.py" "python"
    
    run_test "cpu_pi" "node cpu/pi.js" "node"
    run_test "cpu_pi" "python3 cpu/pi.py" "python"

    # I/O Tests
    node io/http_server.js >/dev/null 2>&1 &
    NODE_PID=$!
    python3 io/http_server.py >/dev/null 2>&1 &
    PY_PID=$!
    sleep 5
    
    run_test "io_http" "wrk -t4 -c100 -d5s http://localhost:3000" "node"
    run_test "io_http" "wrk -t4 -c100 -d5s http://localhost:5000" "python"
    
    kill $NODE_PID $PY_PID || true
    
    run_test "io_file" "node io/file_io.js" "node"
    run_test "io_file" "python3 io/file_io.py" "python"

    # Generate report
    echo -e "\nBenchmark Results:"
    jq -r '.tests | to_entries[] | 
    "TEST: \(.key | ascii_upcase)\n" + 
    (.value | to_entries[] | 
    "  \(.key | ascii_upcase): \(.value[].metric // "N/A")")' "$REPORT_FILE"
    
    echo -e "\nFull report: $REPORT_FILE"
}

# Run main function
main