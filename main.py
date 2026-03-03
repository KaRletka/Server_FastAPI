from fastapi import FastAPI
from db import *
from models import *
import uvicorn

db_provider = DBProvider()
app = FastAPI()



@app.post("/api/add_word")
async def add_words(item: Word):
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)