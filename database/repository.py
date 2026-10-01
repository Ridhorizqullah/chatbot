from typing import Any, Dict, List, Optional
from database.supabase_client import get_supabase
from core.logger import logger


class ConsultationRepository:
    """Repository untuk berinteraksi dengan tabel database Supabase."""

    @staticmethod
    async def match_knowledge(
        query_embedding: List[float],
        match_threshold: float = 0.60,
        match_count: int = 3,
        commodity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Melakukan pencarian semantik vektor ke tabel knowledge_base via Supabase RPC."""
        supabase = get_supabase()
        if not supabase:
            return []
        try:
            params = {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "filter_commodity": commodity.lower() if commodity else None
            }
            response = supabase.rpc("match_knowledge", params).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Error saat menjalankan match_knowledge RPC: {e}")
            return []

    @staticmethod
    async def save_consultation_audit(
        phone_number: str,
        farmer_query: str,
        bot_recommendation: Dict[str, Any],
        confidence_score: float,
        is_referred_to_ppl: bool,
        crop_type: Optional[str] = None,
        suspected_disease: Optional[str] = None,
        media_url: Optional[str] = None
    ) -> bool:
        """Menyimpan rekam jejak konsultasi hama/penyakit untuk audit PPL."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            payload = {
                "phone_number": phone_number,
                "crop_type": crop_type,
                "suspected_disease": suspected_disease,
                "confidence_score": confidence_score,
                "is_referred_to_ppl": is_referred_to_ppl,
                "media_url": media_url,
                "farmer_query": farmer_query,
                "bot_recommendation": bot_recommendation
            }
            supabase.table("consultation_audits").insert(payload).execute()
            logger.info(f"Audit konsultasi berhasil disimpan untuk nomor {phone_number}")
            return True
        except Exception as e:
            logger.error(f"Gagal menyimpan rekam jejak konsultasi: {e}")
            return False

    @staticmethod
    async def get_session(phone_number: str) -> Optional[Dict[str, Any]]:
        """Mengambil status sesi percakapan petani."""
        supabase = get_supabase()
        if not supabase:
            return None
        try:
            res = supabase.table("chat_sessions").select("*").eq("phone_number", phone_number).maybe_single().execute()
            return res.data if res else None
        except Exception as e:
            logger.error(f"Gagal mengambil sesi untuk {phone_number}: {e}")
            return None

    @staticmethod
    async def upsert_session(phone_number: str, current_state: Dict[str, Any], last_crop_context: Optional[str] = None) -> bool:
        """Memperbarui status sesi percakapan."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            payload = {
                "phone_number": phone_number,
                "current_state": current_state,
                "last_crop_context": last_crop_context
            }
            supabase.table("chat_sessions").upsert(payload).execute()
            return True
        except Exception as e:
            logger.error(f"Gagal memperbarui sesi untuk {phone_number}: {e}")
            return False

    @staticmethod
    async def get_farmer_consultation_history(phone_number: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Mengambil riwayat konsultasi terakhir seorang petani berdasarkan nomor telepon."""
        supabase = get_supabase()
        if not supabase:
            return []
        try:
            res = (
                supabase.table("consultation_audits")
                .select("created_at, crop_type, suspected_disease, confidence_score, is_referred_to_ppl, bot_recommendation, media_url")
                .eq("phone_number", phone_number)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error(f"Gagal mengambil riwayat konsultasi untuk {phone_number}: {e}")
            return []

    @staticmethod
    async def get_latest_market_prices(commodity: Optional[str] = None, province: Optional[str] = None) -> List[Dict[str, Any]]:
        """Mengambil data harga pasar terkini dari Supabase."""
        supabase = get_supabase()
        if not supabase:
            return []
        try:
            query = supabase.table("market_prices").select("*")
            if commodity:
                query = query.ilike("commodity", f"%{commodity}%")
            if province:
                query = query.ilike("province", f"%{province}%")
            res = query.order("price_date", desc=True).limit(10).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Gagal mengambil data harga pasar: {e}")
            return []

    @staticmethod
    async def upsert_market_price(price_data: Dict[str, Any]) -> bool:
        """Menyimpan atau memperbarui data harga pasar (oleh Admin atau Sistem Otomatis)."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            supabase.table("market_prices").upsert(price_data).execute()
            return True
        except Exception as e:
            logger.error(f"Gagal menyimpan harga pasar: {e}")
            return False

    @staticmethod
    async def update_market_price(price_id: int, updates: Dict[str, Any]) -> bool:
        """Memperbarui data harga pasar spesifik berdasarkan ID."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            res = supabase.table("market_prices").update(updates).eq("id", price_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"Gagal memperbarui harga pasar ID {price_id}: {e}")
            return False

    @staticmethod
    async def delete_market_price(price_id: int) -> bool:
        """Menghapus entri harga pasar berdasarkan ID."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            supabase.table("market_prices").delete().eq("id", price_id).execute()
            return True
        except Exception as e:
            logger.error(f"Gagal menghapus harga pasar ID {price_id}: {e}")
            return False

    @staticmethod
    async def get_all_consultation_audits(referred_only: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """Mengambil rekam jejak konsultasi seluruh petani untuk portal Admin/PPL."""
        supabase = get_supabase()
        if not supabase:
            return []
        try:
            query = supabase.table("consultation_audits").select("*")
            if referred_only:
                query = query.eq("is_referred_to_ppl", True)
            res = query.order("created_at", desc=True).limit(limit).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Gagal mengambil audit konsultasi: {e}")
            return []

    @staticmethod
    async def update_consultation_audit(audit_id: str, updates: Dict[str, Any]) -> bool:
        """Memperbarui status tindak lanjut audit konsultasi (misal oleh petugas PPL)."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            res = supabase.table("consultation_audits").update(updates).eq("id", audit_id).execute()
            return bool(res.data)
        except Exception as e:
            logger.error(f"Gagal memperbarui audit konsultasi ID {audit_id}: {e}")
            return False

    @staticmethod
    async def delete_consultation_audit(audit_id: str) -> bool:
        """Menghapus data audit konsultasi (misal data spam/pengujian)."""
        supabase = get_supabase()
        if not supabase:
            return False
        try:
            supabase.table("consultation_audits").delete().eq("id", audit_id).execute()
            return True
        except Exception as e:
            logger.error(f"Gagal menghapus audit konsultasi ID {audit_id}: {e}")
            return False

