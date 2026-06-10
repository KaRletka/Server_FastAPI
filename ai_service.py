import asyncio
import json
import os
import ssl
from typing import Callable, Awaitable

# Python 3.12+ fix: GigaChat не отправляет TLS close_notify.
# Патчим create_ssl_context в обоих местах: в httpx._config (источник)
# и в httpx._transports.default (локальная ссылка, импортированная до патча).
import httpx._config as _httpx_config
import httpx._transports.default as _httpx_transport
_legacy_flag = getattr(ssl, 'OP_LEGACY_SERVER_CONNECT', 0x4)

_orig_create_ssl_context = _httpx_config.create_ssl_context
def _patched_create_ssl_context(*args, **kwargs):
    ctx = _orig_create_ssl_context(*args, **kwargs)
    ctx.options |= _legacy_flag
    return ctx

_httpx_config.create_ssl_context = _patched_create_ssl_context
_httpx_transport.create_ssl_context = _patched_create_ssl_context

from gigachat import GigaChat
from gigachat.models import Chat, Function, FunctionCall, Messages, MessagesRole
from dotenv import load_dotenv

load_dotenv()

_CREDENTIALS = os.getenv("GIGACHAT_API_KEY", "")
_MODEL       = "GigaChat"
_SCOPE       = "GIGACHAT_API_PERS"
_MAX_TOOL_CALLS = 10

_TOOLS = [
    Function(
        name="get_words",
        description="Поиск слов в словаре пользователя. Без параметров возвращает последние слова.",
        parameters={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Поисковый запрос (слово или перевод). Оставь пустым для получения последних слов."
                }
            }
        }
    ),
    Function(
        name="add_word",
        description=(
            "Добавить новое слово в словарь пользователя. "
            "Всегда самостоятельно заполняй транскрипцию и перевод: "
            "в поле translate перечисли 2-3 наиболее употребительных перевода через запятую. "
            "Поле add_info заполняй ТОЛЬКО если пользователь явно попросил добавить пояснение, пример или заметку."
        ),
        parameters={
            "type": "object",
            "properties": {
                "word":          {"type": "string", "description": "Слово на английском"},
                "transcription": {"type": "string", "description": "Транскрипция в формате МФА, например: həˈloʊ"},
                "translate":     {"type": "string", "description": "2-3 наиболее употребительных перевода через запятую, например: привет, здравствуй"},
                "add_info":      {"type": "string", "description": "Доп. информация: только если пользователь явно попросил (примеры, заметки, контекст)"}
            },
            "required": ["word", "transcription", "translate"]
        }
    ),
    Function(
        name="update_word",
        description=(
            "Обновить существующее слово в словаре пользователя. "
            "При обновлении перевода указывай 2-3 варианта через запятую. "
            "Поле add_info заполняй только если пользователь явно попросил добавить пояснение или пример."
        ),
        parameters={
            "type": "object",
            "properties": {
                "word":          {"type": "string", "description": "Точное написание слова для обновления"},
                "transcription": {"type": "string", "description": "Транскрипция в формате МФА"},
                "translate":     {"type": "string", "description": "2-3 перевода через запятую"},
                "add_info":      {"type": "string", "description": "Доп. информация: только если пользователь явно попросил"}
            },
            "required": ["word", "translate"]
        }
    ),
    Function(
        name="delete_word",
        description="Удалить слово из словаря пользователя.",
        parameters={
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Слово для удаления"}
            },
            "required": ["word"]
        }
    ),
    Function(
        name="update_profile",
        description=(
            "Обновить профиль пользователя. Вызывай когда замечаешь прогресс, "
            "паттерны ошибок, изменения уровня или новую важную информацию о пользователе."
        ),
        parameters={
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "description": "Новый полный текст профиля пользователя"
                }
            },
            "required": ["profile"]
        }
    )
]


def _system_prompt(profile: str) -> str:
    return (
        "Ты — персональный ИИ-ассистент для изучения английского языка.\n\n"
        f"Профиль пользователя:\n{profile or 'Информация ещё не собрана.'}\n\n"
        "У тебя есть инструменты для работы со словарём пользователя. Используй их активно:\n"
        "- get_words — просмотр и поиск слов\n"
        "- add_word — добавить новое слово\n"
        "- update_word — обновить слово\n"
        "- delete_word — удалить слово\n"
        "- update_profile — обновить профиль когда замечаешь прогресс или паттерны\n\n"
        "Правила заполнения слов при добавлении и обновлении:\n"
        "1. word — слово на английском в начальной форме.\n"
        "2. transcription — транскрипция в формате МФА (например: həˈloʊ). Заполняй всегда.\n"
        "3. translate — 2-3 наиболее употребительных перевода через запятую (например: привет, здравствуй). "
        "Заполняй всегда, не жди уточнений от пользователя.\n"
        "4. add_info — заполняй ТОЛЬКО если пользователь явно попросил добавить пример, пояснение или заметку. "
        "В остальных случаях оставляй пустым.\n\n"
        "Веди себя как личный репетитор: помогай запоминать, объясняй, давай примеры."
    )


async def ask_gigachat(
    message: str,
    history: list,
    profile: str,
    tool_executor: Callable[[str, dict], Awaitable[str]]
) -> str:
    loop = asyncio.get_running_loop()

    def _sync_call():
        messages = [Messages(role=MessagesRole.SYSTEM, content=_system_prompt(profile))]

        for msg in history:
            role = MessagesRole.USER if msg["role"] == "user" else MessagesRole.ASSISTANT
            messages.append(Messages(role=role, content=msg["text"]))

        messages.append(Messages(role=MessagesRole.USER, content=message))

        with GigaChat(
            credentials=_CREDENTIALS,
            model=_MODEL,
            scope=_SCOPE,
            verify_ssl_certs=False,
        ) as giga:
            for _ in range(_MAX_TOOL_CALLS):
                payload = Chat(
                    messages=messages,
                    model=_MODEL,
                    functions=_TOOLS,
                    function_call="auto"
                )
                response   = giga.chat(payload)
                choice     = response.choices[0]

                if choice.finish_reason == "function_call":
                    fn_call = choice.message.function_call
                    args_raw = fn_call.arguments
                    fn_args = args_raw if isinstance(args_raw, dict) else json.loads(args_raw)

                    # Вызываем async tool_executor из синхронного потока
                    future = asyncio.run_coroutine_threadsafe(
                        tool_executor(fn_call.name, fn_args), loop
                    )
                    tool_result = future.result(timeout=30)

                    # Добавляем ответ ассистента с вызовом функции
                    messages.append(Messages(
                        role=MessagesRole.ASSISTANT,
                        content=choice.message.content or "",
                        function_call=fn_call
                    ))
                    # Добавляем результат функции (GigaChat требует валидный JSON)
                    messages.append(Messages(
                        role=MessagesRole.FUNCTION,
                        content=json.dumps({"result": tool_result}, ensure_ascii=False),
                        name=fn_call.name
                    ))
                else:
                    return choice.message.content

        return "Не удалось получить ответ."

    for attempt in range(3):
        try:
            return await loop.run_in_executor(None, _sync_call)
        except Exception as exc:
            if attempt == 2:
                raise
            if "SSL" in str(exc) or "ConnectError" in type(exc).__name__:
                await asyncio.sleep(1)
                continue
            raise
