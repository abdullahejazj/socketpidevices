const WebSocket = require("ws");
const fs = require("fs");

const SERVER_URL = "ws://localhost:8888";
const MESSAGE_SIZE = 64;
const INTERVAL = 50;
const NUM_MESSAGES = 1000;
let seq = 1;
let prevRTT = null;
let totalDataSent = 0;
const startTime = Date.now();
const csvFile = "nodejs_test_results.csv";

if (!fs.existsSync(csvFile)) {
    fs.writeFileSync(csvFile, "Sequence,Sent Time,Received Time,RTT (ms),Jitter (ms),Throughput (kbps)\n");
}

const socket = new WebSocket(SERVER_URL);

socket.on("open", () => {
    console.log(`Connected to ${SERVER_URL}`);

    function sendMessage() {
        if (seq > NUM_MESSAGES) {
            console.log("Test completed.");
            socket.close();
            return;
        }

        let sendTime = Date.now();
        let message = `${seq}|${sendTime}|${MESSAGE_SIZE}`.padEnd(MESSAGE_SIZE, " ");
        socket.send(message);

        socket.once("message", (data) => {
            let recvTime = Date.now();
            let rtt = recvTime - sendTime;
            let jitter = prevRTT ? Math.abs(rtt - prevRTT) : 0;
            prevRTT = rtt;

            totalDataSent += Buffer.byteLength(data);
            let elapsedTime = (recvTime - startTime) / 1000;
            let throughput = elapsedTime > 0 ? (totalDataSent * 8) / (elapsedTime * 1000) : 0;

            fs.appendFileSync(csvFile, `${seq},${sendTime},${recvTime},${rtt},${jitter},${throughput}\n`);
        });

        seq++;
        setTimeout(sendMessage, INTERVAL);
    }

    sendMessage();
});

socket.on("close", () => console.log("Disconnected from server"));
socket.on("error", (err) => console.error("Connection error:", err));
