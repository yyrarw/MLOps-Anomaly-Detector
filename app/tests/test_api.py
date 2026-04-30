"""
Integration tests covering all required scenarios for task 7.
Uses FastAPI TestClient with in-memory SQLite — no Docker required.
"""

EMAIL = "test@example.com"
PASSWORD = "testpassword123"
AUTH = (EMAIL, PASSWORD)

MODEL_ID = 1  # ZScoreDetector, cost = 2.0
VALID_ROW = {"metric": "gpu_utilization", "value": 95.0, "node": "node-1", "timestamp": "2024-01-01T00:00:00"}


# ── 1. User registration & authentication ──────────────────────────────────


def test_register_new_user(client):
    r = client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 201
    assert r.json()["email"] == EMAIL


def test_register_duplicate_email(client):
    r = client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 409


def test_login_success(client):
    r = client.get("/users/me", auth=AUTH)
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL


def test_login_wrong_password(client):
    r = client.get("/users/me", auth=(EMAIL, "wrongpassword"))
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.get("/users/me", auth=("nobody@example.com", "pass"))
    assert r.status_code == 401


# ── 2. Balance ─────────────────────────────────────────────────────────────


def test_get_initial_balance(client):
    r = client.get("/balance", auth=AUTH)
    assert r.status_code == 200
    assert r.json()["balance"] == 0.0


def test_top_up_balance(client):
    r = client.post("/balance/top-up", json={"amount": 50.0}, auth=AUTH)
    assert r.status_code == 200
    assert r.json()["balance"] == 50.0


def test_balance_updated_after_top_up(client):
    r = client.get("/balance", auth=AUTH)
    assert r.status_code == 200
    assert r.json()["balance"] == 50.0


# ── 3. ML requests ─────────────────────────────────────────────────────────


def test_predict_success(client):
    r = client.post("/predict", auth=AUTH, json={"model_id": MODEL_ID, "rows": [VALID_ROW]})
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert data["balance"] == 48.0  # 50 - 2 (ZScoreDetector cost)


def test_predict_credits_deducted(client):
    r = client.get("/balance", auth=AUTH)
    assert r.json()["balance"] == 48.0


def test_predict_insufficient_balance(client):
    r = client.post("/auth/register", json={"email": "broke@example.com", "password": "pass12345"})
    assert r.status_code == 201
    r = client.post("/predict", auth=("broke@example.com", "pass12345"),
                    json={"model_id": MODEL_ID, "rows": [VALID_ROW]})
    assert r.status_code == 402


def test_predict_invalid_metric(client):
    r = client.post("/predict", auth=AUTH, json={
        "model_id": MODEL_ID,
        "rows": [{"metric": "unknown_metric", "value": 1.0, "node": "node-1", "timestamp": "2024-01-01T00:00:00"}],
    })
    assert r.status_code == 422


def test_predict_empty_rows(client):
    r = client.post("/predict", auth=AUTH, json={"model_id": MODEL_ID, "rows": []})
    assert r.status_code == 422


def test_predict_missing_node(client):
    r = client.post("/predict", auth=AUTH, json={
        "model_id": MODEL_ID,
        "rows": [{"metric": "gpu_utilization", "value": 1.0, "node": "", "timestamp": "2024-01-01T00:00:00"}],
    })
    assert r.status_code == 422


def test_predict_nonexistent_model(client):
    r = client.post("/predict", auth=AUTH, json={"model_id": 9999, "rows": [VALID_ROW]})
    assert r.status_code == 404


# ── 4. Task detail ─────────────────────────────────────────────────────────


def test_get_task_detail(client):
    r = client.get("/history/predictions", auth=AUTH)
    task_id = r.json()[0]["task_id"]

    r = client.get(f"/history/predictions/{task_id}", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert data["task_id"] == task_id
    assert "status" in data


def test_get_task_detail_not_found(client):
    r = client.get("/history/predictions/99999", auth=AUTH)
    assert r.status_code == 404


# ── 5. History ─────────────────────────────────────────────────────────────


def test_history_predictions(client):
    r = client.get("/history/predictions", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert "task_id" in data[0]
    assert "status" in data[0]


def test_history_transactions(client):
    r = client.get("/history/transactions", auth=AUTH)
    assert r.status_code == 200
    data = r.json()
    types = {t["type"] for t in data}
    assert "topup" in types
    assert "debit" in types


def test_history_transactions_count(client):
    r = client.get("/history/transactions", auth=AUTH)
    data = r.json()
    topups = [t for t in data if t["type"] == "topup"]
    debits = [t for t in data if t["type"] == "debit"]
    assert len(topups) >= 1
    assert len(debits) >= 1
