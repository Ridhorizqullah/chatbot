import unittest
import asyncio
from unittest.mock import patch, AsyncMock
import httpx
from starlette.testclient import TestClient
from api.app import app
from services.whatsapp_service import WhatsAppService


class TestInteractiveMessages(unittest.IsolatedAsyncioTestCase):
    """Pengujian Unit & Integrasi untuk Reply Buttons, List Message, dan Poll."""

    async def asyncSetUp(self):
        self.service = WhatsAppService()
        self.client = TestClient(app)

    @patch("httpx.AsyncClient.post")
    async def test_send_buttons_message_waha_success(self, mock_post):
        """Memverifikasi pengiriman Reply Buttons ke WAHA dengan format payload yang benar."""
        mock_response = httpx.Response(status_code=200, json={"id": "msg_btn_123"})
        mock_post.return_value = mock_response

        buttons = [
            {"id": "btn_cabai", "text": "Cabai"},
            {"id": "btn_padi", "text": "Padi"}
        ]
        result = await self.service.send_buttons_message(
            to_phone="628123456789",
            body="Silakan pilih komoditas:",
            buttons=buttons,
            header="🌾 TaniPintar",
            footer="Tekan tombol di bawah"
        )
        self.assertTrue(result)
        self.assertTrue(mock_post.called)
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs.get("json", {})
        self.assertEqual(payload.get("chatId"), "628123456789@c.us")
        self.assertEqual(len(payload.get("buttons", [])), 2)
        self.assertEqual(payload["buttons"][0]["type"], "reply")
        self.assertEqual(payload["buttons"][0]["text"], "Cabai")

    @patch("httpx.AsyncClient.post")
    async def test_send_list_message_waha_success(self, mock_post):
        """Memverifikasi pengiriman List Message (Menu Daftar) ke WAHA."""
        mock_response = httpx.Response(status_code=200, json={"id": "msg_list_123"})
        mock_post.return_value = mock_response

        sections = [
            {
                "title": "Konsultasi Tanaman",
                "rows": [
                    {"rowId": "menu_cabai", "title": "Cabai", "description": "Diagnosa cabai"},
                    {"rowId": "menu_padi", "title": "Padi", "description": "Diagnosa padi"}
                ]
            }
        ]
        result = await self.service.send_list_message(
            to_phone="628123456789",
            title="Menu Layanan",
            description="Pilih menu:",
            button_text="Pilih Menu",
            sections=sections
        )
        self.assertTrue(result)
        self.assertTrue(mock_post.called)
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs.get("json", {})
        self.assertEqual(payload.get("chatId"), "628123456789@c.us")
        self.assertIn("message", payload)
        self.assertEqual(payload["message"]["button"], "Pilih Menu")
        self.assertEqual(len(payload["message"]["sections"]), 1)

    @patch("httpx.AsyncClient.post")
    async def test_send_poll_message_waha_success(self, mock_post):
        """Memverifikasi pengiriman Poll WhatsApp ke WAHA."""
        mock_response = httpx.Response(status_code=200, json={"id": "msg_poll_123"})
        mock_post.return_value = mock_response

        result = await self.service.send_poll_message(
            to_phone="628123456789",
            question="Tanaman apa yang Anda tanam?",
            options=["Cabai Rawit", "Padi Sawah"]
        )
        self.assertTrue(result)
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs.get("json", {})
        self.assertEqual(payload.get("chatId"), "628123456789@c.us")
        self.assertIn("poll", payload)
        self.assertEqual(payload["poll"]["name"], "Tanaman apa yang Anda tanam?")
        self.assertEqual(len(payload["poll"]["options"]), 2)

    @patch("httpx.AsyncClient.post")
    async def test_send_main_menu_buttons_success(self, mock_post):
        """Memverifikasi pengiriman 4 Tombol Pilihan Cepat Menu Utama TaniPintar."""
        mock_response = httpx.Response(status_code=200, json={"id": "msg_btn_main"})
        mock_post.return_value = mock_response

        result = await self.service.send_main_menu_buttons(to_phone="628123456789")
        self.assertTrue(result)
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs.get("json", {})
        buttons = payload.get("buttons", [])
        self.assertEqual(len(buttons), 4)
        btn_ids = [b["id"] for b in buttons]
        self.assertIn("btn_tanya_penyakit", btn_ids)
        self.assertIn("btn_konsultasi_foto", btn_ids)
        self.assertIn("btn_cek_harga", btn_ids)
        self.assertIn("btn_info_cuaca", btn_ids)

    async def test_graph_greeting_concise_flow(self):
        """Memverifikasi pesan sambutan singkat, padat, dan ramah tanpa daftar 6 layanan panjang."""
        from graph_builder import tani_graph_app
        state = {
            "phone_number": "628999999999",
            "user_message": "halo",
            "media_id": None,
            "media_url": None,
            "intent": "greeting",
            "crop_context": None,
            "is_first_interaction": True,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        result = await tani_graph_app.ainvoke(state)
        reply = result.get("final_response", "")
        self.assertIn("Selamat Datang di TaniPintar Bot", reply)
        # Pastikan daftar 6 layanan yang panjang TIDAK ADA
        self.assertNotIn("6 Layanan Utama yang Dapat Anda Gunakan", reply)
        self.assertNotIn("1. 🔬 *Konsultasi Penyakit Teks:*", reply)

    async def test_graph_photo_instruction_flow(self):
        """Memverifikasi alur 'Konsultasi Foto' tanpa media merespons instruksi foto tidak buram."""
        from graph_builder import tani_graph_app
        state = {
            "phone_number": "628999999999",
            "user_message": "konsultasi foto",
            "media_id": None,
            "media_url": None,
            "intent": "diagnosis",
            "crop_context": None,
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        result = await tani_graph_app.ainvoke(state)
        self.assertEqual(result.get("intent"), "photo_instruction")
        reply = result.get("final_response", "")
        self.assertIn("Silakan kirimkan foto daun atau buah tanaman cabai/padi yang sakit", reply)
        self.assertIn("tidak buram", reply)

    async def test_graph_disease_text_prompt_flow(self):
        """Memverifikasi tombol 'Tanya Penyakit' meminta menceritakan gejala bahasa sehari-hari."""
        from graph_builder import tani_graph_app
        state = {
            "phone_number": "628999999999",
            "user_message": "tanya penyakit",
            "media_id": None,
            "media_url": None,
            "intent": "diagnosis",
            "crop_context": None,
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        result = await tani_graph_app.ainvoke(state)
        self.assertEqual(result.get("intent"), "disease_text_prompt")
        reply = result.get("final_response", "")
        self.assertIn("bahasa sehari-hari", reply)
        self.assertIn("Contoh cerita gejala", reply)

    async def test_graph_price_prompt_flow(self):
        """Memverifikasi tombol 'Cek Harga Pasar' mengarahkan pilihan komoditas."""
        from graph_builder import tani_graph_app
        state = {
            "phone_number": "628999999999",
            "user_message": "cek harga pasar",
            "media_id": None,
            "media_url": None,
            "intent": "market_price",
            "crop_context": None,
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        result = await tani_graph_app.ainvoke(state)
        self.assertEqual(result.get("intent"), "price_prompt")
        reply = result.get("final_response", "")
        self.assertIn("INFORMASI HARGA PASAR HARIAN", reply)

    async def test_graph_weather_prompt_flow(self):
        """Memverifikasi tombol 'Info Cuaca' menanyakan lokasi desa/kecamatan pengguna."""
        from graph_builder import tani_graph_app
        state = {
            "phone_number": "628999999999",
            "user_message": "info cuaca",
            "media_id": None,
            "media_url": None,
            "intent": "weather",
            "crop_context": None,
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        result = await tani_graph_app.ainvoke(state)
        self.assertEqual(result.get("intent"), "weather_prompt")
        reply = result.get("final_response", "")
        self.assertIn("lokasi sawah, desa, atau kecamatan", reply)

    def test_endpoint_test_send_buttons(self):
        """Memverifikasi API endpoint /webhook/test/send-buttons dapat dipanggil."""
        with patch.object(WhatsAppService, "send_buttons_message", return_value=True):
            response = self.client.post(
                "/webhook/test/send-buttons",
                json={"phone": "628123456789", "body": "Pilih menu"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "success")

    def test_endpoint_test_send_list(self):
        """Memverifikasi API endpoint /webhook/test/send-list dapat dipanggil."""
        with patch.object(WhatsAppService, "send_main_menu_list", return_value=True):
            response = self.client.post(
                "/webhook/test/send-list",
                json={"phone": "628123456789"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "success")

    def test_endpoint_test_send_poll(self):
        """Memverifikasi API endpoint /webhook/test/send-poll dapat dipanggil."""
        with patch.object(WhatsAppService, "send_poll_message", return_value=True):
            response = self.client.post(
                "/webhook/test/send-poll",
                json={"phone": "628123456789", "question": "Pilih opsi"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
