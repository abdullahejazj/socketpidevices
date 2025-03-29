# Real-Time Socket Communication Performance Test on Raspberry Pi 4

This project evaluates the real-time performance of socket communication on a Raspberry Pi 4 using both **Python** and **Node.js**. The tests measure various metrics such as latency, jitter, throughput, CPU usage, memory usage, and packet loss.

## 🏗️ **Project Structure**
```plaintext
├── nodejs_server.js     # Node.js WebSocket Server
├── nodejs_client.js     # Node.js WebSocket Client
├── python_server.py     # Python Async Socket Server
├── python_client.py     # Python Async Socket Client
├── README.md            # Documentation
└── results/             # CSV files with test results
```

## 📋 **Test Scenarios**
We conduct three tests:
1. **Node.js Server & Node.js Client**  
2. **Python Server & Python Client**  
3. **Node.js Server & Python Client**  

## 📊 **Performance Metrics**
Each test measures:
- ✅ **Round Trip Time (RTT)** – Latency per message  
- ✅ **Jitter** – Variation in RTT over time  
- ✅ **Throughput** – Data transferred per second  
- ✅ **Packet Loss** – Number of lost messages  
- ✅ **CPU Usage** – System resource consumption  
- ✅ **Memory Usage** – RAM utilization during test  
- ✅ **Message Size Variation** – Small (64B), Medium (1KB), Large (10KB)  
- ✅ **Different Message Intervals** – 10ms, 50ms, 100ms  

## 🚀 **Installation & Setup**
### **1️⃣ Install Dependencies**
#### Node.js Environment
Ensure you have Node.js installed. Then, install required packages:
```sh
npm install ws
```
#### Python Environment
Ensure you have Python 3 installed. Install dependencies using:
```sh
pip install asyncio psutil
```

### **2️⃣ Run Tests**
#### **Test 1: Node.js Server & Node.js Client**
Start the server:
```sh
node nodejs_server.js
```
Start the client:
```sh
node nodejs_client.js
```

#### **Test 2: Python Server & Python Client**
Start the server:
```sh
python python_server.py
```
Start the client:
```sh
python python_client.py
```

#### **Test 3: Node.js Server & Python Client**
Start the Node.js server:
```sh
node nodejs_server.js
```
Start the Python client:
```sh
python python_client.py
```

## 📁 **Results**
Test results are saved in CSV files under the `results/` directory:
- **`nodejs_test_results.csv`**
- **`python_test_results.csv`**
- **`cross_platform_test_results.csv`**

## 📈 **Next Steps**
- 📊 Visualize test results using Matplotlib
- 🌐 Test under WiFi vs. Ethernet
- 🤹 Vary the number of concurrent clients
- ⚡ Optimize performance for real-world applications

## 🤝 **Contributions**
Feel free to open an issue or submit a pull request if you'd like to improve this project!

---
🚀 **Happy Testing!**

