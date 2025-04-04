import { exec } from 'child_process';
import readline from 'readline';
import fs from 'fs/promises';
import path from 'path';

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

class InteractiveTester {
    constructor() {
        this.config = {
            durations: [2, 5, 10],
            repetitions: 1,
            cooldown: 60,
            serverIP: '192.168.4.1'
        };
    }

    async menu() {
        console.clear();
        console.log('=== WebSocket Network Tester ===');
        console.log(`1) Run single test (current reps: ${this.config.repetitions})`);
        console.log(`2) Run all standard tests (${this.config.durations.join(', ')} min)`);
        console.log('3) Configure repetitions');
        console.log('4) Configure cooldown');
        console.log('5) Exit');
        
        const choice = await this.question('Select option: ');
        
        switch(choice) {
            case '1':
                await this.runSingleTest();
                break;
            case '2':
                await this.runAllTests();
                break;
            case '3':
                await this.configureRepetitions();
                break;
            case '4':
                await this.configureCooldown();
                break;
            case '5':
                process.exit(0);
            default:
                console.log('Invalid option');
        }
        
        await this.question('Press Enter to continue...');
        this.menu();
    }

    async runSingleTest() {
        const duration = await this.question(
            `Enter duration (${this.config.durations.join(', ')} or custom): `, 
            parseInt
        );
        
        for (let i = 0; i < this.config.repetitions; i++) {
            console.log(`\nStarting test ${i+1}/${this.config.repetitions} (${duration} min)`);
            await this.runTest(duration);
            
            if (i < this.config.repetitions - 1) {
                console.log(`Cooldown for ${this.config.cooldown} seconds...`);
                await new Promise(res => setTimeout(res, this.config.cooldown * 1000));
            }
        }
    }

    async runAllTests() {
        for (const duration of this.config.durations) {
            for (let i = 0; i < this.config.repetitions; i++) {
                console.log(`\nStarting test ${i+1}/${this.config.repetitions} (${duration} min)`);
                await this.runTest(duration);
                
                if (i < this.config.repetitions - 1 || 
                    duration !== this.config.durations[this.config.durations.length - 1]) {
                    console.log(`Cooldown for ${this.config.cooldown} seconds...`);
                    await new Promise(res => setTimeout(res, this.config.cooldown * 1000));
                }
            }
        }
    }

    async runTest(duration) {
        // Start server in background
        const serverProcess = exec(
            `node server.mjs ${duration}`,
            { stdio: 'inherit' }
        );
        
        // Wait for server to start
        await new Promise(res => setTimeout(res, 3000));
        
        // Start client
        await new Promise((resolve) => {
            const clientProcess = exec(
                `node client.mjs ${duration}`,
                { stdio: 'inherit' },
                (error) => {
                    if (error) console.error('Client error:', error);
                    resolve();
                }
            );
        });
        
        serverProcess.kill();
    }

    async configureRepetitions() {
        const reps = await this.question(
            'Enter number of repetitions (1-10): ',
            input => Math.min(10, Math.max(1, parseInt(input) || 1))
        );
        this.config.repetitions = reps;
        console.log(`Set repetitions to ${reps}`);
    }

    async configureCooldown() {
        const cooldown = await this.question(
            'Enter cooldown in seconds (30-600): ',
            input => Math.min(600, Math.max(30, parseInt(input) || 60))
        );
        this.config.cooldown = cooldown;
        console.log(`Set cooldown to ${cooldown} seconds`);
    }

    question(prompt, parser = x => x) {
        return new Promise(resolve => {
            rl.question(prompt, answer => {
                resolve(parser(answer));
            });
        });
    }
}

// Create results directory
await fs.mkdir('results', { recursive: true });

// Start interactive tester
const tester = new InteractiveTester();
tester.menu().catch(console.error);