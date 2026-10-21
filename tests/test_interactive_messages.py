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
    async def test_send_main_menu_list_waha_6_features(self, mock_post):
        """Memverifikasi pengiriman WhatsApp List Message utama 6 fitur via WAHA /api/sendList."""
        mock_response = httpx.Response(status_code=200, json={"id": "msg_list_main"})
        mock_post.return_value = mock_response

        result = await self.service.send_welcome_menu(to_phone="628123456789")
        self.assertTrue(result)
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs.get("json", {})
        self.assertEqual(payload.get("chatId"), "628123456789@c.us")
        msg_obj = payload.get("message", {})
        sections = msg_obj.get("sections", [])
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["title"], "Layanan TaniPintar")
        rows = sections[0].get("rows", [])
        self.assertEqual(len(rows), 6)
        row_ids = [r["rowId"] for r in rows]
        expected_ids = [
            "btn_tanya_penyakit",
            "btn_konsultasi_foto",
            "btn_cek_harga",
            "btn_info_cuaca",
            "btn_pupuk",
            "btn_riwayat"
        ]
        self.assertEqual(row_ids, expected_ids)

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

    @patch("httpx.AsyncClient.post")
    async def test_send_welcome_menu_single_message_and_reply_to(self, mock_post):
        """Memverifikasi send_welcome_menu mengirimkan 1 pesan utuh List Message 6 fitur dan quote pesan (reply_to)."""
        mock_response = httpx.Response(status_code=200, json={"id": "msg_welcome_123"})
        mock_post.return_value = mock_response

        result = await self.service.send_welcome_menu(
            to_phone="628123456789",
            reply_to="wamid_user_msg_001",
            prefix_notice="⏱️ _Sesi sebelumnya telah berakhir karena tidak ada interaksi selama 30 menit._"
        )
        self.assertTrue(result)
        self.assertEqual(mock_post.call_count, 1)  # Tepat 1 kali kirim pesan tunggal
        call_kwargs = mock_post.call_args.kwargs
        payload = call_kwargs.get("json", {})
        self.assertEqual(payload.get("chatId"), "628123456789@c.us")
        self.assertEqual(payload.get("reply_to"), "wamid_user_msg_001")
        msg_obj = payload.get("message", {})
        desc = msg_obj.get("description", "")
        self.assertIn("Sesi sebelumnya telah berakhir", desc)
        self.assertIn("Selamat Datang di TaniPintar", desc)
        sections = msg_obj.get("sections", [])
        self.assertEqual(len(sections), 1)
        self.assertEqual(len(sections[0].get("rows", [])), 6)

    @patch("httpx.AsyncClient.post")
    async def test_typing_indicator_presence(self, mock_post):
        """Memverifikasi pemanggilan presence start_typing dan stop_typing ke WAHA API."""
        mock_post.return_value = httpx.Response(status_code=200, json={"status": "ok"})

        start_ok = await self.service.start_typing(to_phone="628123456789")
        self.assertTrue(start_ok)

        stop_ok = await self.service.stop_typing(to_phone="628123456789")
        self.assertTrue(stop_ok)

    @patch("api.routes.whatsapp.whatsapp_service.send_welcome_menu", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.send_text_message", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.start_typing", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.stop_typing", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.send_seen", new_callable=AsyncMock)
    async def test_process_incoming_message_single_welcome_message(
        self, mock_seen, mock_stop, mock_start, mock_text, mock_welcome
    ):
        """Memverifikasi bahwa event greeting hanya memicu 1 kali pesan tunggal (tidak double message)."""
        from api.routes.whatsapp import process_incoming_message
        mock_welcome.return_value = True

        await process_incoming_message(
            phone_number="628123456789",
            message_text="menu",
            msg_id="incoming_msg_999"
        )

        mock_start.assert_called_once()
        mock_welcome.assert_called_once_with(
            to_phone="628123456789",
            session=None,
            reply_to="incoming_msg_999",
            prefix_notice=None
        )
        mock_text.assert_not_called()  # Pastikan TIDAK ADA pesan teks ganda yang dikirim
        mock_stop.assert_called_once()

    @patch("services.session_service.SessionService.update_session_state", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.send_text_message", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.send_welcome_menu", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.start_typing", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.stop_typing", new_callable=AsyncMock)
    @patch("api.routes.whatsapp.whatsapp_service.send_seen", new_callable=AsyncMock)
    async def test_numeric_and_button_menu_choices_1_to_6(
        self, mock_seen, mock_stop, mock_start, mock_welcome, mock_text, mock_update_state
    ):
        """Memverifikasi bahwa pilihan menu 1-6 dan ID tombol btn_... membalas instruksi yang tepat dengan footer hint tanpa mengirim ulang menu (Stateless Direct)."""
        from api.routes.whatsapp import process_incoming_message
        mock_text.return_value = True
        mock_update_state.return_value = True

        test_cases = [
            ("1", "KONSULTASI HAMA & PENYAKIT"),
            ("btn_tanya_penyakit", "KONSULTASI HAMA & PENYAKIT"),
            ("2", "KONSULTASI FOTO TANAMAN"),
            ("btn_konsultasi_foto", "KONSULTASI FOTO TANAMAN"),
            ("3", "HARGA PASAR"),
            ("btn_cek_harga", "HARGA PASAR"),
            ("4", "PREDIKSI CUACA"),
            ("btn_info_cuaca", "PREDIKSI CUACA"),
            ("5", "PANDUAN DOSIS PUPUK"),
            ("btn_pupuk", "PANDUAN DOSIS PUPUK"),
            ("6", "REKAM JEJAK KONSULTASI"),
            ("btn_riwayat", "REKAM JEJAK KONSULTASI"),
        ]

        for choice, expected_snippet in test_cases:
            mock_text.reset_mock()
            mock_welcome.reset_mock()
            mock_update_state.reset_mock()

            with patch("services.session_service.SessionService.evaluate_incoming_message", new_callable=AsyncMock) as mock_eval, \
                 patch("database.repository.ConsultationRepository.upsert_session", new_callable=AsyncMock) as mock_repo_upsert, \
                 patch("database.repository.ConsultationRepository.get_farmer_consultation_history", new_callable=AsyncMock) as mock_repo_hist:
                mock_eval.return_value = (False, "active", {"current_state": {"step": "main_menu"}})
                mock_repo_upsert.return_value = True
                mock_repo_hist.return_value = []

                await process_incoming_message(
                    phone_number="628123456789",
                    message_text=choice,
                    msg_id=f"msg_id_{choice}"
                )

                # 1. State Supabase diperbarui (khusus cek harga masuk ke awaiting_price_commodity)
                expected_step = "awaiting_price_commodity" if choice in ["3", "btn_cek_harga"] else "main_menu"
                mock_update_state.assert_called_once_with(
                    phone_number="628123456789",
                    step=expected_step,
                    crop_context=None
                )

                # 2. Harus membalas instruksi yang tepat, me-quote pesan (reply_to), dan menyertakan footer hint
                call_texts = [call.kwargs.get("text", "") for call in mock_text.call_args_list]
                self.assertTrue(any(expected_snippet.upper() in t.upper() for t in call_texts))
                self.assertTrue(any("💡 Ketik *menu*" in t for t in call_texts))
                for call in mock_text.call_args_list:
                    self.assertEqual(call.kwargs.get("to_phone"), "628123456789")
                    self.assertEqual(call.kwargs.get("reply_to"), f"msg_id_{choice}")

                # 3. Menu utama TIDAK BOLEH dikirim ulang
                mock_welcome.assert_not_called()

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
