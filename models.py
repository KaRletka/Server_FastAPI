from pydantic import BaseModel


# Модель, используется для валидации слов (аааааааа бомбовое коментирование)
class Word(BaseModel):
    word: str
    transcription: str
    translate: str
    add_info: str | None = None

# Модель, используется для запросов с поиском слова, я передаю данные в формате json,
# поэтому пришлось писать отдельную модель

class SWord(BaseModel): #Full name - Search_word
    word: str | None = None
    translate: str | None = None