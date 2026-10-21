from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from database.repository import ConsultationRepository
from core.logger import logger

# Kata kunci pintas global untuk reset navigasi bot ke menu utama
GLOBAL_RESET_KEYWORDS = {
    "menu", "mulai", "awal", "batal", "reset", "start",
    "btn_menu", "btn_menu_utama"
}

# Batas waktu timeout sesi inaktif (30 menit)
SESSION_TIMEOUT_MINUTES = 30


class SessionService:
    """
    Service manajemen sesi percakapan petani, timeout otomatis 30 menit,
    dan reset global sesuai panduan UX WhatsApp Bot TaniPintar.
    """

    @staticmethod
    def is_global_reset_keyword(text: str) -> bool:
        """Memeriksa apakah teks pesan merupakan kata kunci reset global."""
        clean = (text or "").lower().strip()
        return clean in GLOBAL_RESET_KEYWORDS

    @staticmethod
    def is_session_timed_out(session_data: Optional[Dict[str, Any]], timeout_minutes: int = SESSION_TIMEOUT_MINUTES) -> bool:
        """
        Memeriksa apakah selisih waktu now() - updated_at telah melebihi timeout_minutes (30 menit).
        """
        if not session_data or not session_data.get("updated_at"):
            return False

        try:
            updated_at_val = session_data["updated_at"]
            if isinstance(updated_at_val, str):
                # Tangani format ISO dari Supabase (contoh: '2026-10-21T14:15:00+00:00')
                clean_ts = updated_at_val.replace("Z", "+00:00")
                last_time = datetime.fromisoformat(clean_ts)
            elif isinstance(updated_at_val, datetime):
                last_time = updated_at_val
            else:
                return False

            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            delta_seconds = (now - last_time).total_seconds()
            return delta_seconds > (timeout_minutes * 60)
        except Exception as e:
            logger.debug(f"Gagal memeriksa timeout sesi: {e}")
            return False

    @classmethod
    async def evaluate_incoming_message(
        cls,
        phone_number: str,
        message_text: str
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Mengevaluasi pesan masuk terhadap tabel user_sessions di Supabase:
        - Jika pesan berisi kata kunci reset ("menu", "mulai", "awal", "batal"), ATAU
        - Jika sesi inaktif > 30 menit (timeout):
          -> Perbarui current_state menjadi {"step": "main_menu"}
          -> Return: (True, 'global_reset_keyword' | 'session_timeout', session_data)
        - Jika sesi masih aktif (< 30 menit) dan bukan kata kunci reset:
          -> Return: (False, 'active', session_data)
        """
        session_data = await ConsultationRepository.get_session(phone_number)

        # 1. Cek Kata Kunci Pintas Global
        if cls.is_global_reset_keyword(message_text):
            logger.info(f"[SessionManager] Pesan '{message_text}' memicu global reset ke main_menu untuk {phone_number}")
            await ConsultationRepository.upsert_session(
                phone_number=phone_number,
                current_state={"step": "main_menu"},
                last_crop_context=session_data.get("last_crop_context") if session_data else None
            )
            return True, "global_reset_keyword", session_data

        # 2. Cek Timeout 30 Menit
        if cls.is_session_timed_out(session_data):
            logger.info(f"[SessionManager] Sesi {phone_number} telah inaktif > 30 menit. Auto-reset ke main_menu.")
            await ConsultationRepository.upsert_session(
                phone_number=phone_number,
                current_state={"step": "main_menu"},
                last_crop_context=session_data.get("last_crop_context") if session_data else None
            )
            return True, "session_timeout", session_data

        return False, "active", session_data

    @classmethod
    async def update_session_state(
        cls,
        phone_number: str,
        step: str = "main_menu",
        crop_context: Optional[str] = None,
        state_dict: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Memperbarui posisi menu aktif (step) dan timestamp updated_at."""
        final_state = state_dict if state_dict is not None else {"step": step}
        return await ConsultationRepository.upsert_session(
            phone_number=phone_number,
            current_state=final_state,
            last_crop_context=crop_context
        )
