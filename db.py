import aiosqlite
from models import *
from pathlib import Path
import logging
from functools import wraps

PATH_TO_DB = Path("/var/lib/server_fastapi/dictionary.sqlite")
# PATH_TO_DB = Path("dictionary.sqlite")
logger = logging.getLogger("db")


def log_db_operation(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info(f"{func.__name__} called with args={args[1:]}, kwargs={kwargs}")

        try:
            result = await func(*args, **kwargs)
            logger.info(f"{func.__name__} success")
            return result

        except Exception:
            logger.exception(f"{func.__name__} failed")
            raise

    return wrapper

class DBProvider:

    @staticmethod
    def connection(func):
        async def wrapper(*args, **kwargs):
            async with aiosqlite.connect(PATH_TO_DB) as db:
                return await func(*args, *kwargs, db=db)
        return wrapper

    @log_db_operation
    @connection
    async def add_word(self, item: Word, db):
        item = item.model_dump()
        await db.execute("INSERT INTO words VALUES (NULL, ?, ?, ?, ?)", (*item.values(),))
        await db.commit()
        return {'Status': 'Ok', 'info': ''}

    @log_db_operation
    @connection
    async def del_word(self, pointer: int, db): #IDE ругается, id зарезервированное слово
        await db.execute("DELETE FROM words WHERE id=?", (pointer,))
        await db.commit()
        return {'Status': 'Ok', 'info': ''}

    @log_db_operation
    @connection
    async def get_words(self, page: int, db):
        cursor = await db.execute("SELECT * FROM words ORDER BY id DESC LIMIT 15;")
        result_json = {}
        async for row in cursor:
            result_json[row[0]] = [
                row[1],
                row[2],
                row[3],
                row[4] if len(row) == 5 else ''
            ]
        return result_json

    @log_db_operation
    @connection
    async def update_word(self, item: Word, db):
        item = item.model_dump()
        pointer = item.pop(0)
        await db.execute("UPDATE words SET word=?, transcription=?, translate=?, addition=? WHERE id=?",
                              (*item.values(), pointer,))
        await db.commit()
        return {'Status': 'Ok', 'info': ''}

    @log_db_operation
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