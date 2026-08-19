import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://127.0.0.1:8340/ws/voice"
    try:
        async with websockets.connect(uri) as ws:
            print("Connected.")
            msg = {"type": "transcript", "text": "open youtube", "isFinal": True}
            await ws.send(json.dumps(msg))
            
            while True:
                response = await ws.recv()
                data = json.loads(response)
                print(f"Received: {data.get('type')}")
                if data.get('type') == 'audio':
                    print("Received audio!")
                    break
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test_ws())
