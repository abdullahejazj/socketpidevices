import asyncio
import websockets
import time

async def test_latency(url, test_num):
    try:
        start = time.perf_counter()
        async with websockets.connect(url) as ws:
            await ws.send("ping")
            response = await ws.recv()
            if response != "pong":
                raise ValueError("Invalid response")
            return time.perf_counter() - start
    except Exception as e:
        print(f"Test {test_num} failed ({url}): {str(e)}")
        return None

async def main():
    servers = [
        ("Node.js", "ws://10.120.233.229:3001"),
        ("Python", "ws://10.120.233.229:5001")
    ]
    
    for name, url in servers:
        print(f"\nTesting {name} server...")
        latencies = []
        for i in range(10):  # 5 test connections
            latency = await test_latency(url, i+1)
            if latency is not None:
                latencies.append(latency)
        
        if latencies:
            avg = sum(latencies) / len(latencies)
            print(f"Success rate: {len(latencies)}/100")
            print(f"Average latency: {avg*1000:.2f}ms")
        else:
            print("All connection attempts failed")

if __name__ == '__main__':
    asyncio.run(main())