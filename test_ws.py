import asyncio
import websockets
import json

async def main():
    uri = 'ws://127.0.0.1:8001/ws/chat/1/'
    async with websockets.connect(uri) as ws:
        print('Connected')
        await ws.send(json.dumps({'user': 'testclient', 'content': 'hello'}))
        msg = await ws.recv()
        print('Received', msg)

if __name__ == '__main__':
    asyncio.run(main())
