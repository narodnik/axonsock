import asyncio
import random
import sys

MAGIC_BYTES = b"\xd9\xef\xb6\x7d"

COMMAND_SAYHELLO = 0
COMMAND_PING = 1
COMMAND_PONG = 2
COMMAND_REPLY = 3
COMMAND_PUBLISH = 4
COMMAND_REQUEST = 5

MAX_UINT32 = 2**32 - 1

def parse_addr(addr):
    addr = addr.split(":")
    assert len(addr) == 2
    return addr[0], int(addr[1])

class ClosedRemote(Exception):
    pass

class Remote:

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def read_packet(self):
        magic = await self.reader.readexactly(4)
        if magic != MAGIC_BYTES:
            return None
        command = await self.reader.readexactly(1)
        command = int.from_bytes(command, "big")
        payload_len = await self.reader.readexactly(4)
        payload_len = int.from_bytes(payload_len, "big")
        payload = await self.reader.readexactly(payload_len)
        return Packet(command, payload, self)

    async def send_packet(self, command, payload):
        self.writer.write(MAGIC_BYTES)
        assert command < 256 and command >= 0
        command = (command).to_bytes(1, "big")
        self.writer.write(command)
        payload_len = (len(payload)).to_bytes(4, "big")
        self.writer.write(payload_len)
        self.writer.write(payload)

    async def make_request(self, command, payload):
        return await self.send_packet(command, payload)

    def addr(self):
        return self.writer.get_extra_info('peername')

class Packet:

    def __init__(self, command, payload, remote):
        self.command = command
        self.payload = payload
        self._remote = remote

    async def respond(self, payload):
        assert self.command > COMMAND_REQUEST
        assert len(self.payload) >= 4
        request_id_data = self.payload[:4]
        payload = request_id_data + payload

        await self._remote.send_packet(COMMAND_REPLY, payload)

    def remote(self):
        return self._remote

    def __repr__(self):
        return "<Packet command=%s payload=%s>" % (self.command, self.payload)

class Server:

    def __init__(self):
        self._recv = asyncio.Queue()
        self._publish = asyncio.Queue()

    async def bind(self, addr):
        server = await asyncio.start_server(self._accept, *parse_addr(addr))

        addr = server.sockets[0].getsockname()
        print("Serving on:", addr)

        self.bind_task = asyncio.create_task(self._serve(server))

    async def receive(self):
        return await self._recv.get()

    async def publish(self, payload):
        await self._publish.put(payload)

    async def _serve(self, server):
        async with server:
            await server.serve_forever()

    async def _accept(self, reader, writer):
        remote = Remote(reader, writer)
        print("Connected to", remote.addr())

        #packet = await self.read_packet(reader, writer)
        #if packet is None or packet.command != COMMAND_SAYHELLO:
        #    print("Unexpected initial packet command", file=sys.stderr)
        #    return
        #await self._recv.put(packet)

        #await self.send_packet(writer, COMMAND_SAYHELLO, b"")

        self.publish_task = asyncio.create_task(self._publish_process(remote))
        self.read_task = asyncio.create_task(self._read_process(remote))

    async def _publish_process(self, remote):
        while True:
            payload = await self._publish.get()
            await remote.send_packet(COMMAND_PUBLISH, payload)

    async def _read_process(self, remote):
        while True:
            packet = await remote.read_packet()
            await self._recv.put(packet)

class Client:

    def __init__(self):
        self._main_recv = asyncio.Queue()
        self._recvs = [self._main_recv]

    async def connect(self, addr):
        try:
            connection = await asyncio.open_connection(*parse_addr(addr))
        except ConnectionRefusedError:
            raise ClosedRemote()
        self.remote = Remote(*connection)

        print("Connected to", self.remote.addr())

        self.read_task = asyncio.create_task(self._read_process(self.remote))

    async def receive(self):
        return await self._main_recv.get()

    async def make_request(self, command, payload):
        recv = asyncio.Queue()
        self._recvs.append(recv)

        # Prepend random request ID
        request_id = random.randint(0, MAX_UINT32)
        payload = request_id.to_bytes(4, "big") + payload

        await self.remote.make_request(command, payload)

        while True:
            packet = await recv.get()
            if packet.command != COMMAND_REPLY:
                continue

            if len(packet.payload) < 4:
                print("Error malformed packet", file=sys.stderr)
                self.remote.writer.close()
                raise ClosedRemote()

            id_data, data = packet.payload[:4], packet.payload[4:]
            response_id = int.from_bytes(id_data, "big")
            if response_id != request_id:
                continue

            self._recvs.remove(recv)
            return data

    async def _read_process(self, remote):
        while True:
            packet = await remote.read_packet()
            [await recv.put(packet) for recv in self._recvs]

