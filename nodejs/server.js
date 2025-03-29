const WebSocket = require("ws");

const PORT = 8888;
const server = new WebSocket.Server({ port: PORT });

console.log(`Node.js Server running on ws://localhost:${PORT}`);

server.on("connection", (ws) => {
    console.log("Client connected");

    ws.on("message", (message) => {
        ws.send(message); // Echo back
    });

    ws.on("close", () => console.log("Client disconnected"));
});
