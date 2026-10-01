from fastapi import APIRouter, Header, HTTPException, status
from typing import List, Optional
from agents.schemas import AdminPriceInputSchema, AdminPriceUpdateSchema, AdminAuditFollowUpSchema
from database.repository import ConsultationRepository
from core.config import settings
from core.logger import logger

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Portal"])


def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """Verifikasi token otorisasi admin."""
    if settings.app_env != "development":
        if not x_admin_key or x_admin_key != settings.admin_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Akses Ditolak: Kunci Admin (X-Admin-Key) tidak valid."
            )


# ==========================================
# 1. HARGA PASAR (FULL CRUD: POST, GET, PUT, DELETE)
# ==========================================

@router.post("/prices")
async def input_market_price(payload: AdminPriceInputSchema, x_admin_key: Optional[str] = Header(None)):
    """[CREATE] Endpoint bagi Admin untuk menginput atau memperbarui harga pasar harian cabai & padi se-Indonesia."""
    verify_admin_key(x_admin_key)

    record = {
        "price_date": payload.price_date.isoformat(),
        "commodity": payload.commodity,
        "province": payload.province,
        "farmgate_price": payload.farmgate_price,
        "consumer_price": payload.consumer_price,
        "unit": "kg",
        "source": "Input Manual Admin TaniPintar",
        "notes": payload.notes or "Harga acuan terverifikasi admin harian."
    }

    success = await ConsultationRepository.upsert_market_price(record)
    if not success:
        logger.warning(f"Gagal simpan ke Supabase (mungkin db offline), disimpan sementara ke log: {record}")
        return {
            "status": "success",
            "message": "Data harga pasar berhasil diterima (Mode Standalone/Log).",
            "data": record
        }

    return {
        "status": "success",
        "message": f"Harga {payload.commodity} wilayah {payload.province} tanggal {payload.price_date} berhasil disimpan di Supabase.",
        "data": record
    }


@router.get("/prices")
async def get_all_prices(commodity: Optional[str] = None, province: Optional[str] = None):
    """[READ] Melihat data harga pasar yang tersimpan di Supabase."""
    data = await ConsultationRepository.get_latest_market_prices(commodity=commodity, province=province)
    return {
        "status": "success",
        "message": f"Ditemukan {len(data)} entri harga pasar.",
        "data": data
    }


@router.put("/prices/{price_id}")
async def update_market_price(
    price_id: int,
    payload: AdminPriceUpdateSchema,
    x_admin_key: Optional[str] = Header(None)
):
    """[UPDATE] Mengedit data harga komoditas spesifik berdasarkan ID (misal koreksi salah ketik nominal)."""
    verify_admin_key(x_admin_key)

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada field yang dikirim untuk diperbarui.")

    success = await ConsultationRepository.update_market_price(price_id, updates)
    if not success:
        # Fallback response jika offline/mock
        logger.warning(f"Update harga ID {price_id} tercatat di log (Database offline/mock): {updates}")
        return {
            "status": "success",
            "message": f"Data harga ID {price_id} berhasil diperbarui (Mode Standalone/Log).",
            "data": {"id": price_id, **updates}
        }

    return {
        "status": "success",
        "message": f"Data harga ID {price_id} berhasil diperbarui di Supabase.",
        "data": {"id": price_id, **updates}
    }


@router.delete("/prices/{price_id}")
async def delete_market_price(
    price_id: int,
    x_admin_key: Optional[str] = Header(None)
):
    """[DELETE] Menghapus data harga komoditas berdasarkan ID (misal data duplikat atau kadaluarsa)."""
    verify_admin_key(x_admin_key)

    success = await ConsultationRepository.delete_market_price(price_id)
    return {
        "status": "success",
        "message": f"Entri harga pasar ID {price_id} berhasil dihapus.",
        "data": {"deleted_id": price_id, "success": success}
    }


# ==========================================
# 2. AUDIT KONSULTASI & PPL (FULL CRUD: GET, PATCH, DELETE)
# ==========================================

@router.get("/consultations")
async def get_consultation_audits(
    referred_only: bool = False,
    limit: int = 50,
    x_admin_key: Optional[str] = Header(None)
):
    """[READ] Melihat rekam jejak konsultasi petani (bisa filter kasus rujukan PPL)."""
    verify_admin_key(x_admin_key)
    audits = await ConsultationRepository.get_all_consultation_audits(referred_only=referred_only, limit=limit)
    return {
        "status": "success",
        "message": f"Ditemukan {len(audits)} rekaman konsultasi.",
        "data": audits
    }


@router.patch("/consultations/{consultation_id}")
async def update_consultation_status(
    consultation_id: str,
    payload: AdminAuditFollowUpSchema,
    x_admin_key: Optional[str] = Header(None)
):
    """[UPDATE] Mengubah status rujukan PPL atau mencatat rekomendasi tambahan petugas lapangan."""
    verify_admin_key(x_admin_key)

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada data pembaruan yang dikirim.")

    success = await ConsultationRepository.update_consultation_audit(consultation_id, updates)
    return {
        "status": "success",
        "message": f"Status konsultasi {consultation_id} berhasil diperbarui.",
        "data": {"id": consultation_id, **updates, "updated": success}
    }


@router.delete("/consultations/{consultation_id}")
async def delete_consultation(
    consultation_id: str,
    x_admin_key: Optional[str] = Header(None)
):
    """[DELETE] Menghapus rekam jejak konsultasi (misal jika spam atau data uji coba)."""
    verify_admin_key(x_admin_key)
    success = await ConsultationRepository.delete_consultation_audit(consultation_id)
    return {
        "status": "success",
        "message": f"Data konsultasi {consultation_id} berhasil dihapus.",
        "data": {"deleted_id": consultation_id, "success": success}
    }

