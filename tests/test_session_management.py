import unittest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from services.session_service import SessionService, GLOBAL_RESET_KEYWORDS
from database.repository import ConsultationRepository
from graph_builder import tani_graph_app, FOOTER_MENU_HINT


class TestSessionManagement(unittest.IsolatedAsyncioTestCase):
    """Pengujian Unit & Integrasi Manajemen Sesi, Timeout 30 Menit, dan Footer Hint."""

    def test_global_reset_keywords(self):
        """Memverifikasi seluruh kata kunci pintas reset global dikenali."""
        for kw in ["menu", "mulai", "awal", "batal", "reset", "start", "MENU", "  batal  "]:
            self.assertTrue(
                SessionService.is_global_reset_keyword(kw),
                f"Kata kunci '{kw}' harus dikenali sebagai reset global."
            )

        for non_kw in ["cabai saya layu", "harga pasar", "cuaca sleman"]:
            self.assertFalse(
                SessionService.is_global_reset_keyword(non_kw),
                f"Teks '{non_kw}' tidak boleh dianggap sebagai reset global."
            )

    def test_session_timeout_calculation(self):
        """Memverifikasi deteksi sesi kedaluwarsa (> 30 menit)."""
        now = datetime.now(timezone.utc)

        # 1. Sesi aktif (baru 5 menit yang lalu) -> Tidak Timeout
        active_time = (now - timedelta(minutes=5)).isoformat()
        active_session = {"phone_number": "628111", "updated_at": active_time}
        self.assertFalse(SessionService.is_session_timed_out(active_session))

        # 2. Sesi kedaluwarsa (35 menit yang lalu) -> Timeout
        expired_time = (now - timedelta(minutes=35)).isoformat()
        expired_session = {"phone_number": "628222", "updated_at": expired_time}
        self.assertTrue(SessionService.is_session_timed_out(expired_session))

        # 3. Sesi baru tanpa updated_at -> Tidak Timeout
        self.assertFalse(SessionService.is_session_timed_out(None))
        self.assertFalse(SessionService.is_session_timed_out({}))

    @patch.object(ConsultationRepository, "get_session")
    @patch.object(ConsultationRepository, "upsert_session", return_value=True)
    async def test_evaluate_incoming_message_keyword_reset(self, mock_upsert, mock_get):
        """Memverifikasi pesan kata kunci reset langsung mereset current_state ke main_menu."""
        mock_get.return_value = {
            "phone_number": "628123456789",
            "current_state": {"step": "waiting_for_photo"},
            "last_crop_context": "cabai",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        should_reset, reason, data = await SessionService.evaluate_incoming_message(
            phone_number="628123456789",
            message_text="batal"
        )
        self.assertTrue(should_reset)
        self.assertEqual(reason, "global_reset_keyword")
        # Pastikan upsert dipanggil dengan current_state main_menu
        mock_upsert.assert_called_with(
            phone_number="628123456789",
            current_state={"step": "main_menu"},
            last_crop_context="cabai"
        )

    @patch.object(ConsultationRepository, "get_session")
    @patch.object(ConsultationRepository, "upsert_session", return_value=True)
    async def test_evaluate_incoming_message_timeout_reset(self, mock_upsert, mock_get):
        """Memverifikasi sesi > 30 menit otomatis di-reset ke main_menu."""
        expired_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        mock_get.return_value = {
            "phone_number": "628123456789",
            "current_state": {"step": "waiting_for_photo"},
            "last_crop_context": "padi",
            "updated_at": expired_time
        }

        should_reset, reason, data = await SessionService.evaluate_incoming_message(
            phone_number="628123456789",
            message_text="apakah ini obatnya?"
        )
        self.assertTrue(should_reset)
        self.assertEqual(reason, "session_timeout")
        mock_upsert.assert_called_with(
            phone_number="628123456789",
            current_state={"step": "main_menu"},
            last_crop_context="padi"
        )

    async def test_footer_hint_in_long_responses(self):
        """Memverifikasi balasan informasi panjang menyertakan catatan kaki UX 'menu'."""
        # 1. Output Harga Pasar
        state_price = {
            "phone_number": "628999999999",
            "user_message": "harga cabai rawit merah",
            "media_id": None,
            "media_url": None,
            "intent": "market_price",
            "crop_context": "cabai",
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        res_price = await tani_graph_app.ainvoke(state_price)
        reply_price = res_price.get("final_response", "")
        self.assertIn("Ketik *'menu'* kapan saja jika ingin kembali ke halaman utama", reply_price)

        # 2. Output Cuaca
        state_weather = {
            "phone_number": "628999999999",
            "user_message": "cuaca di sleman",
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
        res_weather = await tani_graph_app.ainvoke(state_weather)
        reply_weather = res_weather.get("final_response", "")
        self.assertIn("Ketik *'menu'* kapan saja jika ingin kembali ke halaman utama", reply_weather)


if __name__ == "__main__":
    unittest.main()
