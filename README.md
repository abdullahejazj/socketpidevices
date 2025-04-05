# Real-Time Socket Communication Performance Test on Raspberry Pi 4

This project evaluates the real-time performance of socket communication on a Raspberry Pi 4 using both **Python** and **Node.js**. The tests measure various metrics such as latency, jitter, throughput, CPU usage, memory usage, and packet loss.

## 🏗️ **Project Structure**
```plaintext
├── server.js     # Node.js Socket Server
├── client.js     # Node.js Socket Client
├── server.py     # Python Async Socket Server
├── client.py     # Python Async Socket Client
├── README.md     # Documentation
└── results/      # CSV files with test results
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
- ✅ **Concurrent Clients** – Test with multiple clients  
- ✅ **Network Conditions** – LAN vs. WiFi impact  

## 🚀 **Installation & Setup**

### **1️⃣ Install Dependencies**
#### **Node.js Environment**
Ensure you have Node.js installed.
```sh
sudo apt update && sudo apt install -y nodejs npm
```
Install required packages:
```sh
npm install net
```

#### **Python Environment**
Ensure you have Python 3 installed. Install dependencies using:
```sh
sudo apt update && sudo apt install -y python3 python3-pip
pip install asyncio psutil
```

### **2️⃣ Set Up the Raspberry Pi for Testing**
1. Ensure your Raspberry Pi is connected to a **stable network** (Ethernet or WiFi).
2. Set up a directory for the project:
   ```sh
   mkdir socket_test && cd socket_test
   ```
3. Clone or download this repository:
   ```sh
   git clone <repository_url>
   cd <repository_folder>
   ```

### **3️⃣ Run Tests**
#### **Test 1: Node.js Server & Node.js Client**
1. Start the **Node.js server**:
   ```sh
   node server.js
   ```
2. Start the **Node.js client** in another terminal:
   ```sh
   node client.js
   ```

#### **Test 2: Python Server & Python Client**
1. Start the **Python server**:
   ```sh
   python3 server.py
   ```
2. Start the **Python client** in another terminal:
   ```sh
   python3 client.py
   ```

#### **Test 3: Node.js Server & Python Client**
1. Start the **Node.js server**:
   ```sh
   node server.js
   ```
2. Start the **Python client**:
   ```sh
   python3 client.py
   ```

### **4️⃣ Saving Test Results**
- The test results are automatically logged and stored in CSV files under the `results/` directory:
  - **`nodejs_test_results.csv`**
  - **`python_test_results.csv`**
  - **`cross_platform_test_results.csv`**

### **5️⃣ Analyzing Performance Data**
1. Open the results directory:
   ```sh
   cd results
   ```
2. View the contents of a CSV file:
   ```sh
   cat nodejs_test_results.csv
   ```
3. Optionally, use Python to generate plots from the data:
   ```sh
   python3 analyze_results.py
   ```

## 🤝 **Contributions**
Feel free to open an issue or submit a pull request if you'd like to improve this project!

---
🚀 **Happy Testing!**

