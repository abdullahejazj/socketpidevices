// Node.js
const start = Date.now();
const arr = new Array(25_000_000).fill().map((_, i) => i * 2); // ~100MB
const sum = arr.reduce((acc, val) => acc + val, 0);
console.log(`Time: ${(Date.now() - start) / 1000}s`);