// Node.js (Express)
const express = require('express');
const app = express();

app.get('/', (req, res) => res.send('Hello'));
app.listen(3000, '0.0.0.0', () => console.log('Server running'));