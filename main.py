import json
import os
import time
import logging
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

from db import *
from models import *
from ai_service import ask_gigachat
import user_data_service as uds

load_dotenv()

PATH_TO_LOGFILE = os.getenv("LOG_PATH", "api.log")

logging.basicConfig(
    filename=PATH_TO_LOGFILE,
    level=logging.INFO,
    filemode="w",
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("api")

db_provider = DBProvider()
security    = HTTPBearer()


async def fetch_transcription(word: str) -> str:
    """Получает IPA-транскрипцию слова из Free Dictionary API. Возвращает '' если не найдено."""
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower().strip()}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return ""
        data = resp.json()
        for entry in data:
            for phonetic in entry.get("phonetics", []):
                text = phonetic.get("text", "").strip()
                if text:
                    return text.strip("/.")
    except Exception:
        pass
    return ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_provider.init_db()
    yield


app = FastAPI(lifespan=lifespan)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = await db_provider.get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


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


# --- Auth ---

@app.post("/auth/register", status_code=201)
async def register(user: UserRegister):
    token = await db_provider.register_user(user.login, user.password)
    if token is None:
        raise HTTPException(status_code=409, detail="Login already taken")
    user_info = await db_provider.get_user_by_token(token)
    uds.init_user(user_info["id"])
    return {"token": token}


@app.post("/auth/login")
async def login(user: UserRegister):
    token = await db_provider.login_user(user.login, user.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid login or password")
    return {"token": token}


# --- Words ---

@app.post("/api/words")
async def add_word(item: Word, user=Depends(get_current_user)):
    return await db_provider.add_word(user["id"], item)


@app.delete("/api/words/{word_id}")
async def del_word(word_id: int, user=Depends(get_current_user)):
    return await db_provider.del_word(user["id"], word_id)


@app.put("/api/words/{word_id}")
async def update_word(word_id: int, item: Word, user=Depends(get_current_user)):
    return await db_provider.update_word(user["id"], word_id, item)


@app.get("/api/words")
async def get_words(
    page: int = 1,
    word: str = None,
    translate: str = None,
    user=Depends(get_current_user)
):
    if word is not None or translate is not None:
        return await db_provider.search_word(user["id"], SWord(word=word, translate=translate))
    return await db_provider.get_words(user["id"], page)


@app.get("/api/words/{word_id}")
async def get_word(word_id: int, user=Depends(get_current_user)):
    return await db_provider.get_word(user["id"], word_id)


# --- Dialogs ---

@app.get("/api/dialogs")
async def list_dialogs(user=Depends(get_current_user)):
    uds.init_user(user["id"])
    return uds.list_dialogs(user["id"])


@app.post("/api/dialogs", status_code=201)
async def create_dialog(user=Depends(get_current_user)):
    dialog_id = uds.create_dialog(user["id"])
    return {"id": dialog_id}


@app.patch("/api/dialogs/{dialog_id}")
async def rename_dialog(dialog_id: str, body: DialogRename, user=Depends(get_current_user)):
    if not uds.rename_dialog(user["id"], dialog_id, body.name):
        raise HTTPException(status_code=404, detail="Dialog not found")
    return {"status": "ok"}


@app.delete("/api/dialogs/{dialog_id}")
async def delete_dialog(dialog_id: str, user=Depends(get_current_user)):
    if not uds.delete_dialog(user["id"], dialog_id):
        raise HTTPException(status_code=404, detail="Dialog not found")
    return {"status": "ok"}


@app.get("/api/dialogs/{dialog_id}")
async def get_dialog(dialog_id: str, user=Depends(get_current_user)):
    dialog = uds.get_dialog(user["id"], dialog_id)
    if dialog is None:
        raise HTTPException(status_code=404, detail="Dialog not found")
    return dialog


@app.post("/api/dialogs/{dialog_id}/message")
async def send_message(dialog_id: str, request: MessageRequest, user=Depends(get_current_user)):
    dialog = uds.get_dialog(user["id"], dialog_id)
    if dialog is None:
        raise HTTPException(status_code=404, detail="Dialog not found")

    profile = uds.read_profile(user["id"])
    history = dialog["messages"]

    async def tool_executor(name: str, args: dict) -> str:
        if name == "get_words":
            search = args.get("search")
            if search:
                by_word      = await db_provider.search_word(user["id"], SWord(word=search, translate=None))
                by_translate = await db_provider.search_word(user["id"], SWord(word=None, translate=search))
                result = {**by_translate, **by_word}  # совпадение по слову приоритетнее
            else:
                result = await db_provider.get_words(user["id"], 1)
            if not result:
                return "Слова не найдены."
            lines = [f"{wid}: {v[0]} — {v[2]}" for wid, v in result.items()]
            return "\n".join(lines)

        if name == "add_word":
            transcription = await fetch_transcription(args["word"]) or args.get("transcription", "")
            item = Word(
                word=args["word"],
                transcription=transcription,
                translate=args["translate"],
                add_info=args.get("add_info", "")
            )
            await db_provider.add_word(user["id"], item)
            return f"Слово «{args['word']}» добавлено. Транскрипция: {transcription or 'не найдена'}."

        if name == "update_word":
            row = await db_provider.find_word_by_name(user["id"], args["word"])
            if not row:
                return f"Слово «{args['word']}» не найдено в словаре."
            transcription = await fetch_transcription(args["word"]) or args.get("transcription", row[3] or "")
            item = Word(
                word=args["word"],
                transcription=transcription,
                translate=args.get("translate", row[4] or ""),
                add_info=args.get("add_info", row[5] or "")
            )
            await db_provider.update_word(user["id"], row[0], item)
            return f"Слово «{args['word']}» обновлено. Транскрипция: {transcription or 'не найдена'}."

        if name == "delete_word":
            row = await db_provider.find_word_by_name(user["id"], args["word"])
            if not row:
                return f"Слово «{args['word']}» не найдено."
            await db_provider.del_word(user["id"], row[0])
            return f"Слово «{args['word']}» удалено."

        if name == "update_profile":
            uds.write_profile(user["id"], args["profile"])
            return "Профиль обновлён."

        return f"Неизвестный инструмент: {name}"

    answer = await ask_gigachat(request.text, history, profile, tool_executor)
    uds.append_messages(user["id"], dialog_id, request.text, answer)
    return {"response": answer}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
