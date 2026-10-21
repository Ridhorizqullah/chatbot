import json
import uuid
import numpy as np
from typing import Any, Dict, List, Optional
from database.supabase_client import get_supabase
from core.logger import logger


def _is_valid_uuid(val: Any) -> bool:
    """Memvalidasi apakah string merupakan format UUID yang valid untuk PostgreSQL."""
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class ConsultationRepository:
    """Repository untuk berinteraksi dengan tabel database Supabase."""

    _kb_cache: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def _get_local_kb_records(cls) -> List[Dict[str, Any]]:
        """Mengambil dan meng-cache 11 record knowledge_base untuk fallback instan di RAM."""
        if cls._kb_cache is not None:
            return cls._kb_cache
        supabase = get_supabase()
        if not supabase:
            return []
        try:
            res = supabase.table("knowledge_base").select("*").execute()
            if res and res.data:
                cls._kb_cache = res.data
                logger.info(f"Berhasil memuat cache lokal {len(res.data)} data knowledge_base.")
                return cls._kb_cache
        except Exception as e:
            logger.error(f"Gagal memuat cache knowledge_base dari Supabase: {e}")
        return []

    @classmethod
    def _match_knowledge_fallback(
        cls,
        query_embedding: List[float],
        match_threshold: float = 0.50,
        match_count: int = 3,
        commodity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fallback pencarian cosine similarity lokal jika Supabase RPC bermasalah."""
        records = cls._get_local_kb_records()
        if not records or not query_embedding:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        results = []
        for r in records:
            if commodity and r.get("commodity", "").lower() != commodity.lower():
                continue

            raw_emb = r.get("embedding")
            if not raw_emb:
                continue

            try:
                emb = np.array(json.loads(raw_emb) if isinstance(raw_emb, str) else raw_emb, dtype=np.float32)
                emb_norm = np.linalg.norm(emb)
                if emb_norm == 0:
                    continue
                sim = float(np.dot(q_vec, emb) / (q_norm * emb_norm))
                if sim >= match_threshold:
                    item = dict(r)
                    item["similarity"] = sim
                    results.append(item)
            except Exception as ex:
                logger.debug(f"Gagal parse embedding baris KB id {r.get('id')}: {ex}")

        results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
        return results[:match_count]

    @classmethod
    async def match_knowledge(
        cls,
        query_embedding: List[float],
        match_threshold: float = 0.50,
        match_count: int = 3,
        commodity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Melakukan pencarian semantik vektor ke tabel knowledge_base via Supabase RPC atau fallback lokal."""
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
            if response and response.data:
                return response.data
        except Exception as e:
            logger.warning(f"RPC match_knowledge belum siap ({e}). Menggunakan komputasi cosine lokal...")
        
        # Jalankan fallback cosine similarity lokal
        return cls._match_knowledge_fallback(
            query_embedding=query_embedding,
            match_threshold=match_threshold,
            match_count=match_count,
            commodity=commodity
        )

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
        """Mengambil status sesi percakapan petani dari tabel user_sessions (atau chat_sessions)."""
        supabase = get_supabase()
        if not supabase:
            return None
        for table_name in ["chat_sessions", "user_sessions"]:
            try:
                res = supabase.table(table_name).select("*").eq("phone_number", phone_number).maybe_single().execute()
                if res and res.data:
                    return res.data
            except Exception as e:
                logger.debug(f"Pengecekan sesi pada tabel '{table_name}' ({phone_number}): {e}")
        return None

    @staticmethod
    async def upsert_session(phone_number: str, current_state: Dict[str, Any], last_crop_context: Optional[str] = None) -> bool:
        """Memperbarui status sesi percakapan dan timestamp updated_at ke waktu sekarang (now)."""
        supabase = get_supabase()
        if not supabase:
            return False
        from datetime import datetime, timezone
        payload = {
            "phone_number": phone_number,
            "current_state": current_state,
            "last_crop_context": last_crop_context,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        for table_name in ["chat_sessions", "user_sessions"]:
            try:
                supabase.table(table_name).upsert(payload).execute()
                return True
            except Exception as e:
                logger.debug(f"Gagal upsert sesi ke tabel '{table_name}': {e}. Mencoba tabel alternatif...")
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
    async def get_reference_image(disease_name: str) -> Optional[str]:
        """Mengambil link foto referensi resmi penyakit dari tabel disease_reference_images."""
        supabase = get_supabase()
        if not supabase or not disease_name:
            return None
        try:
            # Gunakan kata kunci inti nama penyakit
            clean_kw = disease_name.split("/")[0].split("(")[0].strip()
            res = (
                supabase.table("disease_reference_images")
                .select("image_url")
                .ilike("disease_name", f"%{clean_kw}%")
                .limit(1)
                .execute()
            )
            if res and res.data and len(res.data) > 0:
                return res.data[0].get("image_url")
            return None
        except Exception as e:
            logger.warning(f"Gagal mengambil foto referensi untuk {disease_name}: {e}")
            return None


    @staticmethod
    async def get_latest_market_prices(commodity: Optional[str] = None, province: Optional[str] = None) -> List[Dict[str, Any]]:
        """Mengambil data harga pasar terkini dari Supabase (hanya tanggal terbaru per komoditas & wilayah)."""
        supabase = get_supabase()
        if not supabase:
            return []
        try:
            query = supabase.table("market_prices").select("*")
            if commodity:
                query = query.ilike("commodity", f"%{commodity}%")
            if province:
                query = query.ilike("province", f"%{province}%")
            res = query.order("price_date", desc=True).limit(30).execute()
            data = res.data or []

            # Deduplikasi agar hanya mengambil tanggal terbaru per (commodity, province)
            seen = set()
            latest_records = []
            for item in data:
                key = (item.get("commodity"), item.get("province"))
                if key not in seen:
                    seen.add(key)
                    latest_records.append(item)
            return latest_records
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
        if not _is_valid_uuid(audit_id):
            logger.warning(f"ID audit konsultasi '{audit_id}' bukan format UUID yang valid.")
            return False

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
        if not _is_valid_uuid(audit_id):
            logger.warning(f"ID audit konsultasi '{audit_id}' bukan format UUID yang valid.")
            return False

        supabase = get_supabase()
        if not supabase:
            return False
        try:
            supabase.table("consultation_audits").delete().eq("id", audit_id).execute()
            return True
        except Exception as e:
            logger.error(f"Gagal menghapus audit konsultasi ID {audit_id}: {e}")
            return False

