import unittest
from starlette.testclient import TestClient
from api.app import app
from core.config import settings


class TestApiEndpoints(unittest.TestCase):
    """Pengujian integrasi endpoint FastAPI untuk TaniPintar Bot."""

    def setUp(self):
        self.client = TestClient(app)

    def test_health_check_endpoint(self):
        """Memverifikasi respons endpoint /health."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("data", data)
        self.assertIn("app_env", data["data"])

    def test_whatsapp_webhook_verification_success(self):
        """Memverifikasi handshake challenge verifikasi Webhook WhatsApp Meta."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.meta_wa_verify_token,
            "hub.challenge": "1234567890"
        }
        response = self.client.get("/webhook", params=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "1234567890")

    def test_whatsapp_webhook_verification_unauthorized(self):
        """Memverifikasi penolakan webhook jika verify token salah."""
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token_secret",
            "hub.challenge": "1234567890"
        }
        response = self.client.get("/webhook", params=params)
        self.assertEqual(response.status_code, 403)

    def test_whatsapp_incoming_message_post(self):
        """Memverifikasi penerimaan pesan teks dari WhatsApp Meta."""
        sample_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "100000000000001",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "6280000000000",
                                    "phone_number_id": "9999999999999"
                                },
                                "contacts": [{"profile": {"name": "Pak Petani"}, "wa_id": "628123456789"}],
                                "messages": [
                                    {
                                        "from": "628123456789",
                                        "id": "wamid.HBgLMjE=",
                                        "timestamp": "1720000000",
                                        "text": {"body": "halo tanipintar"},
                                        "type": "text"
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }
        response = self.client.post("/webhook", json=sample_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_admin_price_endpoints(self):
        """Memverifikasi endpoint admin input dan ambil harga pasar."""
        price_payload = {
            "price_date": "2026-10-01",
            "commodity": "Cabai Rawit Merah",
            "province": "Jawa Timur",
            "farmgate_price": 40000,
            "consumer_price": 47000,
            "notes": "Harga panen raya Pasar Pare Kediri"
        }
        headers = {"X-Admin-Key": settings.admin_api_key}

        # 1. Post harga baru oleh Admin
        post_res = self.client.post("/api/v1/admin/prices", json=price_payload, headers=headers)
        self.assertEqual(post_res.status_code, 200)
        self.assertEqual(post_res.json()["status"], "success")

        # 2. Get harga pasar
        get_res = self.client.get("/api/v1/admin/prices?commodity=Cabai")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["status"], "success")

        # 3. Update (PUT) harga pasar
        update_payload = {"farmgate_price": 42000, "notes": "Koreksi kenaikan harga sore hari"}
        put_res = self.client.put("/api/v1/admin/prices/1", json=update_payload, headers=headers)
        self.assertEqual(put_res.status_code, 200)
        self.assertEqual(put_res.json()["status"], "success")
        self.assertEqual(put_res.json()["data"]["farmgate_price"], 42000)

        # 4. Delete (DELETE) harga pasar
        del_res = self.client.delete("/api/v1/admin/prices/1", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "success")
        self.assertEqual(del_res.json()["data"]["deleted_id"], 1)

    def test_admin_consultation_endpoints(self):
        """Memverifikasi endpoint admin rekam jejak konsultasi (GET, PATCH, DELETE)."""
        headers = {"X-Admin-Key": settings.admin_api_key}

        # 1. Get consultations list
        get_res = self.client.get("/api/v1/admin/consultations", headers=headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["status"], "success")

        # 2. Patch consultation follow up
        patch_payload = {"is_referred_to_ppl": False, "followup_notes": "Sudah dikunjungi PPL daerah"}
        patch_res = self.client.patch("/api/v1/admin/consultations/test-uuid-123", json=patch_payload, headers=headers)
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["status"], "success")

        # 3. Delete consultation audit
        del_res = self.client.delete("/api/v1/admin/consultations/test-uuid-123", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()

