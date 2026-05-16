import os
import time
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

from db import *
from models import *
from ai_service import ask_gigachat

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
security = HTTPBearer()


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


# --- AI ---

@app.post("/api/chat")
async def chat(request: ChatRequest, user=Depends(get_current_user)):
    answer = await ask_gigachat(request.message)
    return {"response": answer}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
