import asyncio

HOST = "0.0.0.0"
PORT = 8888

async def handle_client(reader, writer):
    addr = writer.get_extra_info("peername")
    print(f"Connected to {addr}")

    while True:
        data = await reader.read(1024)
        if not data:
            break
        writer.write(data)
        await writer.drain()

    print(f"Disconnected from {addr}")
    writer.close()
    await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"Python Server running on {HOST}:{PORT}")
    async with server:
        await server.serve_forever()

asyncio.run(main())
