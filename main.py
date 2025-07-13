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

@app.post("/api/edit_word")
async def edit_word(item: Word, pointer: int):
    await db_provider.edit_word(item, pointer)

@app.post("/api/search_word")
async def get_words(item: SWord):
    return await db_provider.search_word(item)

@app.get("/api/get_words")
async def get_words():
    return await db_provider.get_words()

@app.get("/api/get_word")
async def get_word(pointer: int):
    return await db_provider.get_word(pointer)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)