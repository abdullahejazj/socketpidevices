# simple_ws_server.py
import asyncio
import websockets

async def handler(websocket):
    async for message in websocket:
        if message == "ping":
            await websocket.send("pong")

async def main():
    async with websockets.serve(handler, "0.0.0.0", 5001):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())
