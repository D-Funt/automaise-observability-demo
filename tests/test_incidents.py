from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_incident_start_rejects_unknown_customer():
    response = client.post(
        "/incident/start",
        json={
            "customer": "Customer Z",  # no existe en CUSTOMERS
            "usecase": "billing_complaint",
        },
    )
    assert response.status_code == 422
    assert "unknown customer" in response.json()["detail"]


def test_incident_start_rejects_unknown_usecase():
    response = client.post(
        "/incident/start",
        json={
            "customer": "Customer C",
            "usecase": "unknown_usecase",  # no existe en USE_CASES
        },
    )
    assert response.status_code == 422
    assert "unknown usecase" in response.json()["detail"]


def test_incident_start_rejects_unknown_channel():
    response = client.post(
        "/incident/start",
        json={
            "customer": "Customer C",
            "usecase": "billing_complaint",
            "channels": [
                "voice",
                "unknown_channel",
            ],  # unknown_channel no es válido para billing_complaint
        },
    )
    detail = response.json()["detail"]
    assert response.status_code == 422
    # aserción precisa: el canal inválido está señalado, y el válido (voice) no
    assert "unknown_channel" in detail
    assert "'voice'" not in detail.split("must be a subset of")[0]
