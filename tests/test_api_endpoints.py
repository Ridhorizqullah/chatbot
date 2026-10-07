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

        # 2. Patch consultation follow up (menggunakan format UUID valid)
        test_uuid = "00000000-0000-0000-0000-000000000001"
        patch_payload = {"is_referred_to_ppl": False, "followup_notes": "Sudah dikunjungi PPL daerah"}
        patch_res = self.client.patch(f"/api/v1/admin/consultations/{test_uuid}", json=patch_payload, headers=headers)
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["status"], "success")

        # 3. Delete consultation audit
        del_res = self.client.delete(f"/api/v1/admin/consultations/{test_uuid}", headers=headers)
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "success")

    def test_message_deduplicator_lru_ttl(self):
        """Memverifikasi logika cache de-duplikasi O(1) TTL LRU di core/dedup.py."""
        import asyncio
        from core.dedup import MessageDeDuplicator

        async def run_dedup_test():
            dedup = MessageDeDuplicator(ttl_seconds=2, max_size=3)
            await dedup.clear()

            # Pesan pertama -> Bukan duplikat (False)
            self.assertFalse(await dedup.is_duplicate_or_record("msg_1"))
            # Pesan kedua dengan ID sama -> Duplikat (True)
            self.assertTrue(await dedup.is_duplicate_or_record("msg_1"))

            # ID berbeda -> Bukan duplikat (False)
            self.assertFalse(await dedup.is_duplicate_or_record("msg_2"))
            self.assertFalse(await dedup.is_duplicate_or_record("msg_3"))

            # Kapasitas 3 penuh: jika tambah msg_4, item tertua (msg_1) dieviksi
            self.assertFalse(await dedup.is_duplicate_or_record("msg_4"))

            # None / string kosong tidak dianggap duplikat
            self.assertFalse(await dedup.is_duplicate_or_record(""))
            self.assertFalse(await dedup.is_duplicate_or_record(None))

        asyncio.run(run_dedup_test())

    def test_waha_webhook_events(self):
        """Memverifikasi penanganan event webhook WAHA (message, group filter, fromMe)."""
        from services.whatsapp_service import sanitize_chat_id

        old_secret = settings.waha_hmac_secret
        settings.waha_hmac_secret = ""  # Matikan HMAC sementara untuk menguji logika event
        try:
            # 1. Test sanitasi nomor
            self.assertEqual(sanitize_chat_id("+62 812-3456-7890"), "6281234567890@c.us")
            self.assertEqual(sanitize_chat_id("081234567890"), "6281234567890@c.us")
            self.assertEqual(sanitize_chat_id("120363012345@g.us"), "120363012345@g.us")

            # 2. Test pesan masuk personal normal
            personal_payload = {
                "event": "message",
                "session": "default",
                "payload": {
                    "id": "waha_msg_test_001",
                    "from": "6281234567890@c.us",
                    "fromMe": False,
                    "body": "halo tanipintar"
                }
            }
            res = self.client.post("/webhook/waha", json=personal_payload)
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.json()["status"], "success")

            # 3. Test pesan grup diabaikan untuk Anti-Ban
            group_payload = {
                "event": "message",
                "session": "default",
                "payload": {
                    "id": "waha_msg_test_002",
                    "from": "120363099999999999@g.us",
                    "fromMe": False,
                    "body": "halo grup"
                }
            }
            res_group = self.client.post("/webhook/waha", json=group_payload)
            self.assertEqual(res_group.status_code, 200)
            self.assertIn("Group", res_group.json()["message"])

            # 4. Test pesan outbound (fromMe: true) diabaikan
            outbound_payload = {
                "event": "message",
                "session": "default",
                "payload": {
                    "id": "waha_msg_test_003",
                    "from": "6281234567890@c.us",
                    "fromMe": True,
                    "body": "jawaban bot"
                }
            }
            res_outbound = self.client.post("/webhook/waha", json=outbound_payload)
            self.assertEqual(res_outbound.status_code, 200)
            self.assertIn("Outbound", res_outbound.json()["message"])
        finally:
            settings.waha_hmac_secret = old_secret

    def test_waha_webhook_hmac_verification(self):
        """Memverifikasi penolakan webhook jika HMAC tidak cocok saat HMAC_SECRET diset."""
        import hmac
        import hashlib
        import json

        old_secret = settings.waha_hmac_secret
        try:
            settings.waha_hmac_secret = "secret_kunci_keamanan_test"
            payload = {
                "event": "message",
                "session": "default",
                "payload": {
                    "id": "waha_msg_hmac_001",
                    "from": "6281234567890@c.us",
                    "fromMe": False,
                    "body": "tes keamanan"
                }
            }
            body_bytes = json.dumps(payload).encode("utf-8")

            # 1. Tanpa header -> Ditolak (401)
            res_no_sig = self.client.post("/webhook/waha", content=body_bytes)
            self.assertEqual(res_no_sig.status_code, 401)

            # 2. Header salah -> Ditolak (401)
            res_wrong = self.client.post("/webhook/waha", content=body_bytes, headers={"X-Webhook-Hmac": "invalid_signature"})
            self.assertEqual(res_wrong.status_code, 401)

            # 3. Header benar -> Diterima (200)
            valid_sig = hmac.new(settings.waha_hmac_secret.encode(), body_bytes, hashlib.sha512).hexdigest()
            res_valid = self.client.post("/webhook/waha", content=body_bytes, headers={
                "X-Webhook-Hmac": valid_sig,
                "X-Webhook-Hmac-Algorithm": "sha512"
            })
            self.assertEqual(res_valid.status_code, 200)

        finally:
            settings.waha_hmac_secret = old_secret


if __name__ == "__main__":
    unittest.main()

