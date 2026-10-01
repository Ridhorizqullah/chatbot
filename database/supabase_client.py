from supabase import create_client, Client
from core.config import settings
from core.logger import logger

_supabase_client: Client | None = None


def get_supabase() -> Client | None:
    """Mengembalikan singleton instance Supabase Client dengan service role key atau None jika belum diset."""
    global _supabase_client
    if _supabase_client is None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            logger.warning("Supabase URL atau Service Role Key belum dikonfigurasi di .env")
            return None
        try:
            _supabase_client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_service_role_key
            )
            logger.info("Supabase Client berhasil diinisialisasi.")
        except Exception as e:
            logger.error(f"Gagal menginisialisasi Supabase Client: {e}")
            return None
    return _supabase_client
