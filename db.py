import aiosqlite
from models import *
from pathlib import Path

PATH_TO_DB = Path("/var/lib/server_fastapi/dictionary.sqlite")

class DBProvider:
    @staticmethod
    def connection(func):
        async def wrapper(*args, **kwargs):
            async with aiosqlite.connect(PATH_TO_DB) as db:
                return await func(*args, *kwargs, db=db)
        return wrapper

    @connection
    async def add_word(self, item: Word, db):
        item = item.model_dump()
        await db.execute("INSERT INTO words VALUES (NULL, ?, ?, ?, ?)", (*item.values(),))
        await db.commit()
        return {'Status': 'Ok', 'info': ''}

    @connection
    async def del_word(self, pointer: int, db): #IDE ругается, id зарезервированное слово
        await db.execute("DELETE FROM words WHERE id=?", (pointer,))
        await db.commit()
        return {'Status': 'Ok', 'info': ''}

    @connection
    async def get_words(self, db):
        cursor = await db.execute("SELECT * FROM words ORDER BY id DESC;")
        result_json = {}
        async for row in cursor:
            result_json[row[0]] = [
                row[1],
                row[2],
                row[3],
                row[4] if len(row) == 5 else ''
            ]
        return result_json

    @connection
    async def edit_word(self, item: Word, pointer, db):
        item = item.model_dump()
        await db.execute("UPDATE words SET word=?, transcription=?, translate=?, addition=? WHERE id=?",
                              (*item.values(), pointer,))
        await db.commit()
        return {'Status': 'Ok', 'info': ''}

    @connection
    async def search_word(self, item: Word, db):
        item = item.model_dump()
        result_json = {}
        if item['word'] == None:
            cursor = await db.execute("SELECT * FROM words WHERE translate LIKE ?",
                             (f"%{item["translate"]}%",))
        elif item['translate'] == None:
            cursor = await db.execute("SELECT * FROM words WHERE word LIKE ?",
                             (f"%{item["word"]}%",))
        else:
            cursor = await db.execute("SELECT * FROM words WHERE word LIKE ? AND translate LIKE ?",
                             (f"%{item["word"]}%", f"%{item["translate"]}%"))
        async for row in cursor:
            result_json[row[0]] = [
                row[1],
                row[2],
                row[3],
                row[4] if len(row) == 5 else ''
            ]
        return result_json

    @connection
    async def get_word(self, pointer: int, db): #IDE ругается, id зарезервированное слово
        result_json = {}
        cursor = await db.execute("SELECT * FROM words WHERE id=?", (pointer,))
        async for row in cursor:
            result_json[row[0]] = [
                row[1],
                row[2],
                row[3],
                row[4] if len(row) == 5 else ''
            ]
        return result_json