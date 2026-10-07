import json
import hmac
import hashlib
import asyncio
from typing import Optional, Set
from fastapi import APIRouter, Request, Query, Response, BackgroundTasks, status
from core.config import settings
from core.logger import logger
from graph_builder import tani_graph_app
from services.whatsapp_service import WhatsAppService
from core.dedup import message_deduplicator

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])
whatsapp_service = WhatsAppService()


def verify_waha_hmac(raw_body: bytes, headers: dict) -> bool:
    """
    Memverifikasi keaslian webhook WAHA menggunakan HMAC SHA-512 / SHA-256
    sesuai standar keamanan WAHA Plus & Webhook Security.
    """
    secret = settings.waha_hmac_secret
    if not secret:
        # Jika belum dikonfigurasi di environment, izinkan untuk kemudahan development lokal
        return True

    # Header signature standar WAHA atau Meta
    signature = (
        headers.get("x-webhook-hmac") or
        headers.get("x-waha-signature") or
        headers.get("x-hub-signature-256") or
        ""
    )
    if not signature:
        # Jika WAHA dikonfigurasi tanpa HMAC signature, izinkan tetapi log warning
        # Ini umum terjadi di WAHA Core (non-Plus) atau konfigurasi webhook tanpa security header
        logger.warning("[WAHA Security] Header HMAC tidak ada di request. Izinkan untuk kompatibilitas WAHA Core.")
        return True

    algo = headers.get("x-webhook-hmac-algorithm", "sha512").lower()
    hash_fn = hashlib.sha512 if "512" in algo else hashlib.sha256

    # Hilangkan prefix 'sha512=' atau 'sha256=' jika ada
    clean_signature = signature.split("=")[-1].strip()
    expected_signature = hmac.new(secret.encode("utf-8"), raw_body, hash_fn).hexdigest()

    return hmac.compare_digest(expected_signature, clean_signature)


@router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Endpoint verifikasi Webhook WhatsApp Cloud API (Meta).
    Meta akan mengirimkan GET request saat pendaftaran webhook di Meta App Dashboard.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_wa_verify_token:
        logger.info("Webhook WhatsApp Meta berhasil diverifikasi!")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Verifikasi Webhook WhatsApp gagal! Token tidak cocok.")
    return Response(content="Verification token mismatch", status_code=status.HTTP_403_FORBIDDEN)


async def process_incoming_message(
    phone_number: str,
    message_text: str,
    media_id: Optional[str] = None,
    session: Optional[str] = None,
    msg_id: Optional[str] = None
):
    """
    Background Task: Menjalankan eksekusi LangGraph & mengirimkan balasan WhatsApp.
    Dijalankan di background agar respon HTTP webhook langsung 200 OK (< 200ms) untuk mencegah timeout.
    """
    try:
        logger.info(f"Memproses pesan dari {phone_number}: '{message_text}' | Media: {media_id} | Session: {session}")

        # 1. Kirim tanda pesan dibaca (centang biru) & tampilkan animasi 'sedang mengetik...' di WA
        await whatsapp_service.send_seen(to_phone=phone_number, message_id=msg_id, session=session)
        await whatsapp_service.start_typing(to_phone=phone_number, session=session)

        # Jalankan LangGraph StateGraph
        initial_state = {
            "phone_number": phone_number,
            "user_message": message_text or "",
            "media_id": media_id,
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

        result = await tani_graph_app.ainvoke(initial_state)
        final_reply = result.get("final_response", "")

        if final_reply:
            # Jeda Alami (Human Typing Delay) untuk Anti-Ban Hygiene
            if settings.waha_human_delay_seconds > 0:
                await asyncio.sleep(settings.waha_human_delay_seconds)

            await whatsapp_service.send_text_message(to_phone=phone_number, text=final_reply, session=session)

    except Exception as e:
        logger.error(f"Gagal memproses pesan di background task: {e}", exc_info=True)
    finally:
        # 2. Hentikan animasi mengetik setelah pemrosesan selesai
        await whatsapp_service.stop_typing(to_phone=phone_number, session=session)


@router.post("")
async def handle_whatsapp_event(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint penerima payload event dari WhatsApp Cloud API.
    Mem-parse pesan teks atau lampiran gambar, lalu mendelegasikannya ke background worker.
    """
    try:
        body = await request.json()

        # Validasi struktur umum payload Meta
        entry = body.get("entry", [])
        if not entry:
            return {"status": "success", "message": "No entry found"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "success", "message": "No changes found"}

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            # Event status pengiriman pesan (sent/delivered/read)
            return {"status": "success", "message": "Status update ignored"}

        msg_obj = messages[0]
        msg_id = msg_obj.get("id")
        if msg_id and await message_deduplicator.is_duplicate_or_record(msg_id):
            logger.info(f"[Meta Webhook] Pesan duplikat diabaikan: {msg_id}")
            return {"status": "success", "message": "Duplicate message ignored"}

        sender_phone = msg_obj.get("from")
        msg_type = msg_obj.get("type")

        extracted_text = ""
        media_id = None

        if msg_type == "text":
            extracted_text = msg_obj.get("text", {}).get("body", "")
        elif msg_type == "image":
            image_obj = msg_obj.get("image", {})
            media_id = image_obj.get("id")
            extracted_text = image_obj.get("caption", "") or "Tolong diagnosa gejala penyakit tanaman pada foto ini."

        if sender_phone:
            # Jadwalkan pemrosesan di background task agar response webhook instan
            background_tasks.add_task(
                process_incoming_message,
                phone_number=sender_phone,
                message_text=extracted_text,
                media_id=media_id
            )

        return {"status": "success", "message": "Event queued for processing"}

    except Exception as e:
        logger.error(f"Error saat menerima webhook WhatsApp: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/waha")
async def handle_waha_event(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint penerima payload webhook event dari WAHA (WhatsApp HTTP API).
    Dilengkapi verifikasi HMAC, filter Anti-Ban grup/broadcast, dan background processing.
    """
    try:
        raw_body = await request.body()

        # 1. Verifikasi Keamanan HMAC Webhook
        if not verify_waha_hmac(raw_body, dict(request.headers)):
            return Response(
                content=json.dumps({"status": "error", "message": "Invalid HMAC signature"}),
                media_type="application/json",
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        event_type = body.get("event")
        payload = body.get("payload", {})

        # 2. Abaikan event selain pesan masuk
        if event_type != "message":
            return {"status": "success", "message": f"Event {event_type} ignored"}

        # 3. Abaikan pesan keluar dari bot sendiri (Anti-Loop)
        if payload.get("fromMe", False):
            return {"status": "success", "message": "Outbound message from bot ignored"}

        from_id = payload.get("from", "")

        # 4. Anti-Ban Filter: Abaikan pesan grup (@g.us), channel (@newsletter), dan broadcast status
        if from_id.endswith("@g.us"):
            logger.info(f"[WAHA Webhook] Pesan grup diabaikan untuk menjaga keamanan nomor: {from_id}")
            return {"status": "success", "message": "Group messages ignored"}

        if from_id.endswith("@newsletter") or from_id == "status@broadcast":
            return {"status": "success", "message": "Channel or status broadcast ignored"}

        # 5. De-duplikasi pesan (Mencegah double processing akibat retry WAHA)
        msg_id = payload.get("id")
        if msg_id and await message_deduplicator.is_duplicate_or_record(msg_id):
            logger.info(f"[WAHA Webhook] Pesan duplikat diabaikan: {msg_id}")
            return {"status": "success", "message": "Duplicate message ignored"}

        # 6. Ekstrak Pengirim, Teks, dan Sesi
        session_name = body.get("session") or settings.waha_session
        sender_phone = from_id
        message_text = payload.get("body", "") or ""

        # Deteksi lampiran media
        media_id = None
        if payload.get("hasMedia"):
            media_obj = payload.get("media") or {}
            media_id = media_obj.get("url")
            if not media_id and msg_id:
                media_id = f"{settings.waha_base_url}/api/{session_name}/chats/{from_id}/messages/{msg_id}/media"

        # Query default untuk foto tanpa caption teks
        if media_id and not message_text.strip():
            message_text = "Tolong diagnosa gejala penyakit tanaman pada foto ini."

        if sender_phone and (message_text or media_id):
            logger.info(f"[WAHA Webhook] Pesan dari {sender_phone}: '{message_text}' | Media: {media_id} | Session: {session_name}")
            background_tasks.add_task(
                process_incoming_message,
                phone_number=sender_phone,
                message_text=message_text,
                media_id=media_id,
                session=session_name,
                msg_id=msg_id
            )

        return {"status": "success", "message": "WAHA event queued for processing"}

    except Exception as e:
        logger.error(f"Error saat menerima webhook WAHA: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
