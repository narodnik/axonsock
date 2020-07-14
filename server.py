import asyncio
import xsock

REQUEST_CLIENT_VERSION = 10
REQUEST_GET_BLOCK_HEIGHT = 11
REQUEST_SEND_MESSAGE = 12

async def start():
    server = xsock.Server()
    await server.bind("127.0.0.1:8888")

    task = asyncio.create_task(handle_requests(server))

    while True:
        await server.publish(b"new block!")
        await asyncio.sleep(1)

async def handle_requests(server):
    while True:
        packet = await server.receive()

        if packet.command == REQUEST_GET_BLOCK_HEIGHT:
            try:
                await packet.respond(b"\x06\x00\x00\x00")

                remote = packet.remote()
                response = await remote.make_request(REQUEST_SEND_MESSAGE, b"hello")
            except xsock.ClosedRemote:
                print("Disconnected. Dropping.")

asyncio.run(start())

