import asyncio
import os

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from dotenv import load_dotenv

load_dotenv()

_CREDENTIALS = os.getenv("GIGACHAT_API_KEY", "")
_MODEL = "GigaChat-Lite"


async def ask_gigachat(message: str) -> str:
    def _call():
        with GigaChat(credentials=_CREDENTIALS, model=_MODEL, verify_ssl_certs=False) as giga:
            payload = Chat(
                messages=[Messages(role=MessagesRole.USER, content=message)],
                model=_MODEL
            )
            response = giga.chat(payload)
            return response.choices[0].message.content

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _call)
