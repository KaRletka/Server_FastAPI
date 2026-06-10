from pydantic import BaseModel


class Word(BaseModel):
    word: str
    transcription: str
    translate: str
    add_info: str


class SWord(BaseModel):
    word: str | None = None
    translate: str | None = None


class UserRegister(BaseModel):
    login: str
    password: str


class ChatRequest(BaseModel):
    message: str


class MessageRequest(BaseModel):
    text: str


class DialogRename(BaseModel):
    name: str
