from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quanthaven.api import app
from quanthaven.security import build_signature


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "signals.db"
        self.db_patch = patch("quanthaven.db.get_settings")
        self.api_patch = patch("quanthaven.api.get_settings")

        mock_db_settings = self.db_patch.start()
        mock_api_settings = self.api_patch.start()

        class Settings:
            disable_auth = True
            webhook_secret = "test-secret"
            database_path = self.database_path
            runtime_dir = Path(self.temp_dir.name)
            data_dir = ROOT / "data"
            artifacts_dir = Path(self.temp_dir.name)

        settings = Settings()
        mock_db_settings.return_value = settings
        mock_api_settings.return_value = settings

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.api_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_accepts_valid_signal(self) -> None:
        response = self.client.post(
            "/webhook/signal",
            json={
                "symbol": "AAPL",
                "side": "buy",
                "qty": "2",
                "price": "150.25",
                "client_order_id": "order-1",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(payload["signal"]["symbol"], "AAPL")

    def test_duplicate_same_payload_returns_duplicate(self) -> None:
        body = {
            "symbol": "AAPL",
            "side": "buy",
            "qty": "2",
            "price": "150.25",
            "client_order_id": "order-1",
        }
        self.assertEqual(self.client.post("/webhook/signal", json=body).status_code, 200)
        second = self.client.post("/webhook/signal", json=body)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "duplicate")

    def test_reused_id_with_different_payload_returns_conflict(self) -> None:
        first = {
            "symbol": "AAPL",
            "side": "buy",
            "qty": "2",
            "price": "150.25",
            "client_order_id": "order-1",
        }
        second = {
            "symbol": "AAPL",
            "side": "sell",
            "qty": "2",
            "price": "150.25",
            "client_order_id": "order-1",
        }
        self.assertEqual(self.client.post("/webhook/signal", json=first).status_code, 200)
        response = self.client.post("/webhook/signal", json=second)
        self.assertEqual(response.status_code, 409)

    def test_invalid_payload_returns_422(self) -> None:
        response = self.client.post("/webhook/signal", json={"symbol": "AAPL", "side": "buy"})
        self.assertEqual(response.status_code, 422)

    def test_rejects_bad_signature_when_auth_enabled(self) -> None:
        class AuthSettings:
            disable_auth = False
            webhook_secret = "test-secret"
            database_path = self.database_path
            runtime_dir = Path(self.temp_dir.name)
            data_dir = ROOT / "data"
            artifacts_dir = Path(self.temp_dir.name)

        with patch("quanthaven.api.get_settings", return_value=AuthSettings()):
            response = self.client.post(
                "/webhook/signal",
                headers={"X-Webhook-Signature": build_signature("wrong-secret", b"{}")},
                content=b'{"symbol":"AAPL","side":"buy","qty":"2","price":"150.25","client_order_id":"signed-1"}',
            )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
