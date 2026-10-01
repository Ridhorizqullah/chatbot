from fastapi import APIRouter, Request, Query, Response, BackgroundTasks, status
from core.config import settings
from core.logger import logger
from graph_builder import tani_graph_app
from services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/webhook", tags=["WhatsApp Webhook"])
whatsapp_service = WhatsAppService()


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


async def process_incoming_message(phone_number: str, message_text: str, media_id: str | None = None):
    """
    Background Task: Menjalankan eksekusi LangGraph & mengirimkan balasan WhatsApp.
    Dijalankan di background agar respon HTTP webhook langsung 200 OK (< 200ms) untuk mencegah timeout Meta.
    """
    try:
        logger.info(f"Memproses pesan dari {phone_number}: '{message_text}' | Media: {media_id}")

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
            await whatsapp_service.send_text_message(to_phone=phone_number, text=final_reply)

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
            extracted_text = image_obj.get("caption", "")

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
