from fastapi import FastAPI, Request
from db import *
from models import *
import uvicorn
import logging
import time

db_provider = DBProvider()
app = FastAPI()

PATH_TO_LOGFILE = "/var/lib/server_fastapi/api.log"

logger = logging.getLogger("api")
logging.basicConfig(
    filename=PATH_TO_LOGFILE,
    level=logging.INFO,
    filemode="w",
    format="%(asctime)s | %(levelname)s | %(message)s"
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    logger.info(f"Request: {request.method} {request.url}")

    response = await call_next(request)

    process_time = time.time() - start_time

    logger.info(
        f"Response: {request.method} {request.url} "
        f"Status: {response.status_code} "
        f"Time: {process_time:.3f}s"
    )

    return response



@app.post("/api/add_word")
async def add_word(item: Word):
    await db_provider.add_word(item)

@app.post("/api/del_word")
async def del_word(pointer: int):
    await db_provider.del_word(pointer)

@app.post("/api/update_word")
async def update_word(item: BaseWord):
    await db_provider.update_word(item)

@app.get("/api/search_word")
async def search_word(item: SWord):
    return await db_provider.search_word(item)

@app.get("/api/get_words")
async def get_words(page):
    return await db_provider.get_words(page)

@app.get("/api/get_word")
async def get_word(pointer: int):
    return await db_provider.get_word(pointer)

# @app.post("/api/ai")
# async def update_word(item: str):
#     return await db_provider.update_word(item)


if __name__ == "__main__":
    PATH_TO_LOGFILE = "api.log"
    uvicorn.run(app, host="127.0.0.1", port=8000)