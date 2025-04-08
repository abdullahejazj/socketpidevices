// Node.js
const fs = require('fs').promises;
const path = require('path');
const { performance } = require('perf_hooks');

async function run() {
    await fs.mkdir('node_files', { recursive: true });
    const start = performance.now();

    // Write 1,000 files
    for (let i = 0; i < 1000; i++) {
        await fs.writeFile(path.join('node_files', `file_${i}.txt`), 'A'.repeat(1048576));
    }

    // Read 1,000 files
    for (let i = 0; i < 1000; i++) {
        await fs.readFile(path.join('node_files', `file_${i}.txt`), 'utf8');
    }

    console.log(`Time: ${(performance.now() - start) / 1000}s`);
}

run();