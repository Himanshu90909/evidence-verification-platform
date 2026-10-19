"""API contract and integration tests for the ML service.

Covers: authentication, input validation, health, model-info, the full
claim -> API -> pipeline -> structured response flow, and error handling.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["corpus_loaded"] is True
    assert data["corpus_documents"] == 8
    assert data["nli_backend"] == "lexical-fallback"


def test_verify_requires_api_key(client):
    res = client.post("/verify", json={"claim": "Paris is the capital of France."})
    assert res.status_code == 401


def test_verify_rejects_wrong_api_key(client):
    res = client.post("/verify", json={"claim": "Paris is the capital of France."},
                      headers={"X-API-Key": "wrong-key"})
    assert res.status_code == 401


def test_verify_accepts_bearer_auth(client, auth_headers):
    res = client.post(
        "/verify",
        json={"claim": "Paris is the capital of France."},
        headers={"Authorization": f"Bearer {auth_headers['X-API-Key']}"},
    )
    assert res.status_code == 200


def test_verify_validates_input(client, auth_headers):
    # too short
    res = client.post("/verify", json={"claim": "hi"}, headers=auth_headers)
    assert res.status_code == 422
    # blank
    res = client.post("/verify", json={"claim": "   "}, headers=auth_headers)
    assert res.status_code == 422
    # bad top_k
    res = client.post("/verify", json={"claim": "A reasonable claim here.", "top_k": 99}, headers=auth_headers)
    assert res.status_code == 422


def test_verify_full_flow(client, auth_headers):
    res = client.post(
        "/verify",
        json={"claim": "The Eiffel Tower is named after the engineer Gustave Eiffel.", "top_k": 3},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    # response contract per project spec
    assert data["verdict"] in ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION")
    assert 0 <= data["confidence"] <= 1
    assert 0 <= data["uncertainty"] <= 1
    assert data["retrieval"]["method"] == "hybrid"
    assert data["retrieval"]["top_k"] == 3
    assert isinstance(data["evidence"], list) and data["evidence"]
    for ev in data["evidence"]:
        assert "document_id" in ev and "text" in ev and "score" in ev and "rank" in ev
        assert ev["source"] and ev["source_url"]
    assert data["model"]["name" if "name" in data["model"] else "model"]
    assert data["model"]["version"]
    assert data["model"]["nli_backend"] == "lexical-fallback"
    assert data["confidence"] + data["uncertainty"] >= 0
    assert data["explanation"]


def test_verify_never_returns_empty_evidence_text(client, auth_headers):
    res = client.post("/verify", json={"claim": "Nikola Tesla held around 300 patents."}, headers=auth_headers)
    for ev in res.json()["evidence"]:
        assert ev["text"].strip()


def test_retrieve_endpoint(client, auth_headers):
    res = client.post("/retrieve", json={"query": "Tesla patents", "top_k": 5, "method": "bm25"}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["retrieval"]["method"] == "bm25"
    assert len(data["evidence"]) >= 1
    assert data["evidence"][0]["document_id"].startswith("Nikola Tesla")


def test_predict_endpoint(client, auth_headers):
    res = client.post(
        "/predict",
        json={"premise": "Paris is the capital of France.", "hypothesis": "Paris is the capital of France."},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["label"] in ("ENTAILMENT", "CONTRADICTION", "NEUTRAL")
    assert abs(sum(data["probabilities"].values()) - 1.0) < 1e-3


def test_explain_endpoint(client, auth_headers):
    res = client.post(
        "/explain",
        json={"claim": "The Great Wall of China was built in a single dynasty."},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data["decision_path"], list) and data["decision_path"]
    assert len(data["per_evidence"]) == len(data["evidence"])


def test_model_info(client, auth_headers):
    res = client.get("/model-info", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["pipeline"]["version"]
    assert data["pipeline"]["embedding_model"]
    assert data["pipeline"]["retriever"]
    assert data["corpus_documents"] == 8
    assert "metrics" in data


def test_metrics_prometheus(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "evp_requests_total" in res.text


def test_cors_configured(client):
    res = client.options(
        "/verify",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
