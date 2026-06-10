import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(os.getenv("USER_DATA_PATH", "user_data"))


def _user_dir(user_id: int) -> Path:
    return _ROOT / str(user_id)


def _dialogs_dir(user_id: int) -> Path:
    return _user_dir(user_id) / "dialogs"


def _profile_path(user_id: int) -> Path:
    return _user_dir(user_id) / "profile.txt"


def _dialog_path(user_id: int, dialog_id: str) -> Path:
    return _dialogs_dir(user_id) / f"{dialog_id}.json"


def init_user(user_id: int):
    """Создаёт папку пользователя и пустой профиль. Идемпотентно."""
    _dialogs_dir(user_id).mkdir(parents=True, exist_ok=True)
    p = _profile_path(user_id)
    if not p.exists():
        p.write_text(
            "Новый пользователь. Информация будет заполнена в ходе общения.",
            encoding="utf-8"
        )


def list_dialogs(user_id: int) -> list:
    d = _dialogs_dir(user_id)
    if not d.exists():
        return []
    result = []
    for f in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "id": f.stem,
                "name": data.get("name", ""),
                "created_at": data.get("created_at", ""),
                "message_count": len(data.get("messages", []))
            })
        except Exception:
            pass
    return result


def create_dialog(user_id: int) -> str:
    init_user(user_id)
    dialog_id = uuid.uuid4().hex[:12]
    dialog = {
        "id": dialog_id,
        "name": "Новый диалог",
        "created_at": datetime.now().isoformat(),
        "messages": []
    }
    _dialog_path(user_id, dialog_id).write_text(
        json.dumps(dialog, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return dialog_id


def get_dialog(user_id: int, dialog_id: str) -> dict | None:
    p = _dialog_path(user_id, dialog_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def rename_dialog(user_id: int, dialog_id: str, name: str) -> bool:
    p = _dialog_path(user_id, dialog_id)
    if not p.exists():
        return False
    dialog = json.loads(p.read_text(encoding="utf-8"))
    dialog["name"] = name
    p.write_text(json.dumps(dialog, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def delete_dialog(user_id: int, dialog_id: str) -> bool:
    p = _dialog_path(user_id, dialog_id)
    if not p.exists():
        return False
    p.unlink()
    return True


def append_messages(user_id: int, dialog_id: str, user_text: str, ai_text: str):
    p = _dialog_path(user_id, dialog_id)
    dialog = json.loads(p.read_text(encoding="utf-8"))
    now = datetime.now().isoformat()
    dialog["messages"].append({"role": "user", "text": user_text, "ts": now})
    dialog["messages"].append({"role": "ai",   "text": ai_text,  "ts": now})
    p.write_text(json.dumps(dialog, ensure_ascii=False, indent=2), encoding="utf-8")


def read_profile(user_id: int) -> str:
    p = _profile_path(user_id)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def write_profile(user_id: int, text: str):
    _profile_path(user_id).write_text(text, encoding="utf-8")
