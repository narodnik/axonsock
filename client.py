import asyncio
import xsock

REQUEST_CLIENT_VERSION = 10
REQUEST_GET_BLOCK_HEIGHT = 11
REQUEST_SEND_MESSAGE = 12

async def start():
    #client = xsock.XSock()
    #await client.connect(('127.0.0.1', 8888))

    while True:
        try:
            client = xsock.Client()
            await client.connect("127.0.0.1:8888")
            # HELLO message sent automatically by the client
            # ping-pong sent in the background

            await protocol(client)

        except xsock.ClosedRemote:
            print("Disconnected. Attempting reconnect.")
            asyncio.sleep(1)

async def protocol(client):
    response = await client.make_request(REQUEST_GET_BLOCK_HEIGHT, b"")

    print("Block height:", response)

    while True:
        packet = await client.receive()

        if packet.command == REQUEST_CLIENT_VERSION:
            await packet.respond(b"6.5.01a")

        elif packet.command == REQUEST_SEND_MESSAGE:
            print("Received:", packet.payload)
            # return OK
            await packet.respond(b"\x00")

        # Handle broadcast messages
        elif packet.command == xsock.COMMAND_PUBLISH:
            print("New update:", packet)

        # elif ...

        # also publish() available for client socket
        # updates can go in both directions
        # they get no reply back.

asyncio.run(start())

