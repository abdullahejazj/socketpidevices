// Node.js
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

function calculatePi(start, end) {
    let sum = 0;
    for (let k = start; k < end; k++) {
        sum += (-1) ** k / (2 * k + 1);
    }
    return sum;
}

if (isMainThread) {
    const start = Date.now();
    const workers = [];
    for (let i = 0; i < 4; i++) {
        workers.push(new Promise((resolve) => {
            const worker = new Worker(__filename, {
                workerData: { start: i * 2_500_000, end: (i + 1) * 2_500_000 }
            });
            worker.on('message', resolve);
        }));
    }
    Promise.all(workers).then((results) => {
        const pi = results.reduce((acc, val) => acc + val, 0) * 4;
        console.log(`Time: ${(Date.now() - start) / 1000}s`);
    });
} else {
    const result = calculatePi(workerData.start, workerData.end);
    parentPort.postMessage(result);
}