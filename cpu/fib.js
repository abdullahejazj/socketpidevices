// Node.js
function fib(n) {
    return n > 1 ? fib(n-1) + fib(n-2) : n;
}

const start = Date.now();
fib(40);
console.log(`Time: ${(Date.now() - start) / 1000}s`);