import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

WORD = {
    "word": "hello",
    "transcription": "həˈloʊ",
    "translate": "привет",
    "add_info": "приветствие",
}


# --- Auth fixtures ---

@pytest.fixture(scope="module")
def auth_headers():
    resp = client.post("/auth/register", json={"login": "testuser", "password": "testpass"})
    assert resp.status_code == 201
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def word_id(auth_headers):
    unique_word = {**WORD, "word": "fixture_word"}
    client.post("/api/words", json=unique_word, headers=auth_headers)
    resp = client.get("/api/words?word=fixture_word", headers=auth_headers)
    return str(list(resp.json().keys())[0])


# --- Auth tests ---

def test_register():
    resp = client.post("/auth/register", json={"login": "newuser", "password": "pass123"})
    assert resp.status_code == 201
    assert "token" in resp.json()


def test_register_duplicate():
    client.post("/auth/register", json={"login": "dupuser", "password": "pass"})
    resp = client.post("/auth/register", json={"login": "dupuser", "password": "pass"})
    assert resp.status_code == 409


def test_login():
    client.post("/auth/register", json={"login": "loginuser", "password": "pass123"})
    resp = client.post("/auth/login", json={"login": "loginuser", "password": "pass123"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password():
    resp = client.post("/auth/login", json={"login": "loginuser", "password": "wrongpass"})
    assert resp.status_code == 401


def test_login_returns_working_token():
    resp = client.post("/auth/login", json={"login": "loginuser", "password": "pass123"})
    token = resp.json()["token"]
    resp = client.get("/api/words?page=1", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_request_without_token():
    resp = client.get("/api/words")
    assert resp.status_code == 403


def test_request_with_invalid_token():
    resp = client.get("/api/words", headers={"Authorization": "Bearer invalidtoken"})
    assert resp.status_code == 401


# --- Words tests ---

def test_add_word(auth_headers):
    resp = client.post("/api/words", json=WORD, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_get_words(auth_headers):
    resp = client.get("/api/words?page=1", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
    assert len(resp.json()) > 0


def test_search_by_word(auth_headers):
    resp = client.get("/api/words?word=hello", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_search_by_translate(auth_headers):
    resp = client.get("/api/words?translate=привет", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_search_combined(auth_headers):
    resp = client.get("/api/words?word=hello&translate=привет", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_get_word(auth_headers, word_id):
    resp = client.get(f"/api/words/{word_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert word_id in resp.json()


def test_update_word(auth_headers, word_id):
    resp = client.put(f"/api/words/{word_id}", json={**WORD, "word": "hi"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_delete_word(auth_headers, word_id):
    resp = client.delete(f"/api/words/{word_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# --- Dialogs tests ---

@pytest.fixture(scope="module")
def dialog_id(auth_headers):
    resp = client.post("/api/dialogs", headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_dialog(auth_headers):
    resp = client.post("/api/dialogs", headers=auth_headers)
    assert resp.status_code == 201
    assert "id" in resp.json()


def test_list_dialogs(auth_headers, dialog_id):
    resp = client.get("/api/dialogs", headers=auth_headers)
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()]
    assert dialog_id in ids


def test_get_dialog(auth_headers, dialog_id):
    resp = client.get(f"/api/dialogs/{dialog_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == dialog_id
    assert "messages" in data


def test_get_dialog_not_found(auth_headers):
    resp = client.get("/api/dialogs/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_dialog(auth_headers):
    resp = client.post("/api/dialogs", headers=auth_headers)
    tmp_id = resp.json()["id"]
    resp = client.delete(f"/api/dialogs/{tmp_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_delete_dialog_not_found(auth_headers):
    resp = client.delete("/api/dialogs/nonexistent", headers=auth_headers)
    assert resp.status_code == 404


def test_rename_dialog(auth_headers, dialog_id):
    resp = client.patch(f"/api/dialogs/{dialog_id}", json={"name": "Мой диалог"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    resp = client.get(f"/api/dialogs/{dialog_id}", headers=auth_headers)
    assert resp.json()["name"] == "Мой диалог"


def test_rename_dialog_not_found(auth_headers):
    resp = client.patch("/api/dialogs/nonexistent", json={"name": "X"}, headers=auth_headers)
    assert resp.status_code == 404
