from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
import threading
from contextlib import asynccontextmanager
import os
import sys






# ---- Определение типа базы данных ----
db_type = "parking"  # значение по умолчанию
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_type = sys.argv[i + 1]
        break








# Абсолютный путь к директории, где лежит server.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Приведение к списку файлов всегда
if db_type == "parking":
    file_paths = [os.path.join(BASE_DIR, "../objects/parking.txt")]
elif db_type == "raillight":
    file_paths = [os.path.join(BASE_DIR, f"../objects/raillight_{i}.txt") for i in range(1, 5)]
elif db_type == "crossroad":
    file_paths = [os.path.join(BASE_DIR, "../objects/crossroad.txt")]
else:
    raise ValueError(f"Unknown db type: {db_type}")

# Абсолютный путь к фронтенду
front_path = os.path.abspath(os.path.join(BASE_DIR, "../pages"))







# ---- Универсальная функция чтения одного файла ----
def read_single_file(file: str, db_type: str):
    with open(file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if db_type == "parking":
        data = {}
        for line in lines:
            parts = line.split(maxsplit=1)
            key, value = (parts[0], None) if len(parts) == 1 else (parts[0], parts[1])
            data[key] = value
        return data

    if db_type == "crossroad":
        data = {}
        first = lines.pop(0).split(maxsplit=1)
        if len(first) == 2:
            data[first[0]] = first[1]
        for line in lines:
            parts = line.split()
            key = parts[0]
            direction = parts[1].rstrip(":")
            values = {parts[i]: int(parts[i+1]) for i in range(2, len(parts), 2)}
            data.setdefault(key, {})[direction] = values
        return data

    if db_type == "raillight":
        return lines  # возвращаем список строк для каждого файла


# ---- Чтение всех файлов ----
def read_file_and_make_dict(file_paths: list, db_type: str):
    if len(file_paths) == 1:
        return read_single_file(file_paths[0], db_type)
    else:
        return {os.path.basename(f): read_single_file(f, db_type) for f in file_paths}







# ---- WebSocket broadcast ----
async def broadcast(data):
    for ws in list(clients):
        try:
            await ws.send_json(data)
        except Exception:
            clients.discard(ws)






# ---- Watchdog ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    global loop
    loop = asyncio.get_running_loop()
    handler = FileChangeHandler()
    observer = Observer()
    for f in file_paths:
        observer.schedule(handler, os.path.dirname(f), recursive=False)
    observer_thread = threading.Thread(target=observer.start, daemon=True)
    observer_thread.start()

    yield

    observer.stop()
    observer.join()


class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        for f in file_paths:
            if os.path.abspath(event.src_path) == os.path.abspath(f):
                data = read_file_and_make_dict(file_paths, db_type)
                asyncio.run_coroutine_threadsafe(broadcast(data), loop)
                break







# ---- FastAPI app ----
app = FastAPI(lifespan=lifespan)

clients = set()


app.mount("/front", StaticFiles(directory=front_path, html=True), name="front")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    await ws.send_json(read_file_and_make_dict(file_paths, db_type))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        clients.discard(ws)

if __name__ == "__main__":
    import uvicorn
    # The --reload flag is great for development, it automatically restarts
    # the server when you save changes to the file.
    uvicorn.run("server:app", host="0.0.0.0", port=801, reload=True)