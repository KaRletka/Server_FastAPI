import hashlib
import os
import secrets

import aiosqlite
import bcrypt
from pathlib import Path
import logging
from functools import wraps
from dotenv import load_dotenv

from models import *
from crypto import encrypt_token, decrypt_token

load_dotenv()

PATH_TO_DB = Path(os.getenv("DB_PATH", "dictionary.sqlite"))
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
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with aiosqlite.connect(PATH_TO_DB) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                return await func(*args, **kwargs, db=db)
        return wrapper

    @log_db_operation
    @connection
    async def init_db(self, db):
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                login           TEXT    UNIQUE NOT NULL,
                password_hash   TEXT    NOT NULL,
                token_hash      TEXT    UNIQUE NOT NULL,
                token_encrypted TEXT    NOT NULL DEFAULT ''
            )
        """)
        # миграция для существующих баз без колонки token_encrypted
        try:
            await db.execute("ALTER TABLE users ADD COLUMN token_encrypted TEXT NOT NULL DEFAULT ''")
        except Exception:
            pass  # колонка уже есть
        await db.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                word          TEXT    NOT NULL,
                transcription TEXT,
                translate     TEXT    NOT NULL,
                addition      TEXT,
                UNIQUE(user_id, word)
            )
        """)
        await db.commit()

    # --- Auth ---

    @log_db_operation
    @connection
    async def register_user(self, login: str, password: str, db):
        cursor = await db.execute("SELECT id FROM users WHERE login=?", (login,))
        if await cursor.fetchone():
            return None  # логин занят

        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        token_encrypted = encrypt_token(raw_token)
        await db.execute(
            "INSERT INTO users (login, password_hash, token_hash, token_encrypted) VALUES (?, ?, ?, ?)",
            (login, password_hash, token_hash, token_encrypted)
        )
        await db.commit()
        return raw_token

    @connection
    async def get_user_by_token(self, raw_token: str, db):
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        cursor = await db.execute(
            "SELECT id, login FROM users WHERE token_hash=?", (token_hash,)
        )
        row = await cursor.fetchone()
        if row:
            return {"id": row[0], "login": row[1]}
        return None

    @log_db_operation
    @connection
    async def login_user(self, login: str, password: str, db):
        cursor = await db.execute(
            "SELECT password_hash, token_encrypted FROM users WHERE login=?", (login,)
        )
        row = await cursor.fetchone()
        if not row:
            return None  # пользователь не найден

        password_hash, token_encrypted = row
        if not bcrypt.checkpw(password.encode(), password_hash.encode()):
            return None  # неверный пароль

        if not token_encrypted:
            return None  # аккаунт создан до добавления шифрования

        return decrypt_token(token_encrypted)

    # --- Words ---

    @connection
    async def find_word_by_name(self, user_id: int, word: str, db):
        """Возвращает (id, word, transcription, translate, addition) или None."""
        cursor = await db.execute(
            "SELECT * FROM words WHERE user_id=? AND word=?",
            (user_id, word)
        )
        return await cursor.fetchone()

    @log_db_operation
    @connection
    async def add_word(self, user_id: int, item: Word, db):
        data = item.model_dump()
        await db.execute(
            "INSERT INTO words (user_id, word, transcription, translate, addition) VALUES (?, ?, ?, ?, ?)",
            (user_id, *data.values())
        )
        await db.commit()
        return {"status": "ok"}

    @log_db_operation
    @connection
    async def del_word(self, user_id: int, word_id: int, db):
        await db.execute(
            "DELETE FROM words WHERE id=? AND user_id=?",
            (word_id, user_id)
        )
        await db.commit()
        return {"status": "ok"}

    @log_db_operation
    @connection
    async def get_words(self, user_id: int, page: int, db):
        page = int(page)
        cursor = await db.execute(
            "SELECT * FROM words WHERE user_id=? ORDER BY id DESC LIMIT 15 OFFSET ?",
            (user_id, (page - 1) * 15)
        )
        result = {}
        async for row in cursor:
            result[row[0]] = [row[2], row[3], row[4], row[5] if len(row) == 6 else ""]
        return result

    @log_db_operation
    @connection
    async def update_word(self, user_id: int, word_id: int, item: Word, db):
        data = item.model_dump()
        await db.execute(
            "UPDATE words SET word=?, transcription=?, translate=?, addition=? WHERE id=? AND user_id=?",
            (*data.values(), word_id, user_id)
        )
        await db.commit()
        return {"status": "ok"}

    @log_db_operation
    @connection
    async def get_word(self, user_id: int, word_id: int, db):
        cursor = await db.execute(
            "SELECT * FROM words WHERE id=? AND user_id=?",
            (word_id, user_id)
        )
        result = {}
        async for row in cursor:
            result[row[0]] = [row[2], row[3], row[4], row[5] if len(row) == 6 else ""]
        return result

    @log_db_operation
    @connection
    async def search_word(self, user_id: int, item: SWord, db):
        data = item.model_dump()
        if data["word"] is None:
            cursor = await db.execute(
                "SELECT * FROM words WHERE user_id=? AND translate LIKE ?",
                (user_id, f"%{data['translate']}%")
            )
        elif data["translate"] is None:
            cursor = await db.execute(
                "SELECT * FROM words WHERE user_id=? AND word LIKE ?",
                (user_id, f"%{data['word']}%")
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM words WHERE user_id=? AND word LIKE ? AND translate LIKE ?",
                (user_id, f"%{data['word']}%", f"%{data['translate']}%")
            )
        result = {}
        async for row in cursor:
            result[row[0]] = [row[2], row[3], row[4], row[5] if len(row) == 6 else ""]
        return result
