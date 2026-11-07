from django.test import Client
from django.urls import reverse


def test_healthz_returns_200_ok(client: Client) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_healthz_head_allowed(client: Client) -> None:
    assert client.head("/healthz").status_code == 200


def test_healthz_rejects_unsafe_methods(client: Client) -> None:
    assert client.post("/healthz").status_code == 405


def test_healthz_is_named_route() -> None:
    assert reverse("healthz") == "/healthz"
