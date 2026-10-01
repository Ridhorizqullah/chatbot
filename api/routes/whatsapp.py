from fastapi import APIRouter, Request, Query, Response, BackgroundTasks, status
from core.config import settings
from core.logger import logger
from graph_builder import tani_graph_app
from services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])
whatsapp_service = WhatsAppService()
_PROCESSED_MESSAGE_IDS: set[str] = set()


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
    media_id: str | None = None,
    session: str | None = None
):
    """
    Background Task: Menjalankan eksekusi LangGraph & mengirimkan balasan WhatsApp.
    Dijalankan di background agar respon HTTP webhook langsung 200 OK (< 200ms) untuk mencegah timeout Meta.
    """
    try:
        logger.info(f"Memproses pesan dari {phone_number}: '{message_text}' | Media: {media_id} | Session: {session}")

        # Jalankan LangGraph StateGraph
        initial_state = {
            "phone_number": phone_number,
            "user_message": message_text or "",
            "media_id": media_id,
            "media_url": None,
            "intent": "diagnosis",
            "crop_context": None,
            "diagnosis_result": None,
            "price_result": None,
            "final_response": ""
        }

        result = await tani_graph_app.ainvoke(initial_state)
        final_reply = result.get("final_response", "")

        if final_reply:
            await whatsapp_service.send_text_message(to_phone=phone_number, text=final_reply, session=session)

    except Exception as e:
        logger.error(f"Gagal memproses pesan di background task: {e}", exc_info=True)


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
    Mendukung WhatsApp Web Scanner (Multi-Device) gratis tanpa Meta Cloud API.
    """
    try:
        body = await request.json()
        event_type = body.get("event")
        payload = body.get("payload", {})

        # Abaikan event selain pesan atau pesan keluar dari bot sendiri
        if event_type != "message":
            return {"status": "success", "message": f"Event {event_type} ignored"}

        if payload.get("fromMe", False):
            return {"status": "success", "message": "Outbound message from bot ignored"}

        # Cegah duplikasi pesan
        msg_id = payload.get("id")
        if msg_id:
            if msg_id in _PROCESSED_MESSAGE_IDS:
                logger.info(f"[WAHA Webhook] Pesan duplikat diabaikan: {msg_id}")
                return {"status": "success", "message": "Duplicate message ignored"}
            _PROCESSED_MESSAGE_IDS.add(msg_id)
            if len(_PROCESSED_MESSAGE_IDS) > 2000:
                _PROCESSED_MESSAGE_IDS.pop()

        # Ekstrak nomor/JID pengirim, teks pesan, dan nama session
        session_name = body.get("session") or settings.waha_session
        from_id = payload.get("from", "")
        # Simpan JID lengkap (misal @lid atau @c.us) agar balasan WAHA terkirim tepat sasaran
        sender_phone = from_id
        message_text = payload.get("body", "") or ""

        media_id = None
        if payload.get("hasMedia"):
            media_obj = payload.get("media") or {}
            media_id = media_obj.get("url")
            if not media_id and msg_id:
                media_id = f"{settings.waha_base_url}/api/{session_name}/chats/{from_id}/messages/{msg_id}/media"

        # Jika pengguna mengirim foto tanpa teks caption, berikan query default agar dianalisa vision
        if media_id and not message_text.strip():
            message_text = "Tolong diagnosa gejala penyakit tanaman pada foto ini."

        if sender_phone and (message_text or media_id):
            logger.info(f"[WAHA Webhook] Pesan dari {sender_phone}: '{message_text}' | Media: {media_id} | Session: {session_name}")
            background_tasks.add_task(
                process_incoming_message,
                phone_number=sender_phone,
                message_text=message_text,
                media_id=media_id,
                session=session_name
            )

        return {"status": "success", "message": "WAHA event queued for processing"}

    except Exception as e:
        logger.error(f"Error saat menerima webhook WAHA: {e}")
        return {"status": "error", "message": str(e)}
