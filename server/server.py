from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
import threading
from contextlib import asynccontextmanager
import os




def read_file_and_make_dict(file_path: str):
    data = {}
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                key, value = parts
            else:
                key, value = parts[0], None
            data[key] = value
    return data



async def broadcast(data: str):
    for ws in list(clients):
        try:
            await ws.send_json(data)
        except Exception:
            clients.discard(ws)






@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop
    loop = asyncio.get_running_loop()
    handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(handler, os.path.dirname(file_path), recursive=False)
    observer_thread = threading.Thread(target=observer.start, daemon=True)
    observer_thread.start()

    yield  # сюда приложение входит в работу

    observer.stop()
    observer.join()


class FileChangeHandler(FileSystemEventHandler):
    """Обработчик событий изменения файла"""
    def on_modified(self, event):
        if event.src_path.endswith(file_path):
            data = read_file_and_make_dict(file_path)
            # пересылка в главный поток asyncio
            asyncio.run_coroutine_threadsafe(broadcast(data), loop)








app = FastAPI(lifespan=lifespan)
file_path = os.path.abspath(r"objects\parking.txt")
front_path = r"pages\\"
#file_path = r"D:\studwork\3 мага\сем1\ИтиКБ\DB\Parking.txt"
#front_path = r"D:\studwork\3 мага\сем1\ИтиКБ\front"
clients = set()


app.mount("/front", StaticFiles(directory=front_path, html=True), name="front")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    await ws.send_json(read_file_and_make_dict(file_path))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)


