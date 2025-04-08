const WebSocket = require('ws');

const server = new WebSocket.Server({ port: 3001 });

server.on('connection', (socket) => {
  console.log('Client connected');
  
  socket.on('message', (message) => {
    if (message.toString() === 'ping') {
      socket.send('pong');
    }
  });

  
});

console.log('WebSocket server running on ws://localhost:3001');