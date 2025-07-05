from pydantic import BaseModel

class Word(BaseModel): # Модель, используется для валидации слов (аааааааа бомбовое коментирование)
    word: str
    transcription: str
    translate: str
    add_info: str | None = None