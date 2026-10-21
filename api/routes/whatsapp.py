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
from services.session_service import SessionService
from core.dedup import message_deduplicator
from core.latency_tracker import LatencyTracker

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
        logger.warning("[WAHA Security] Header HMAC tidak ada di request padahal secret dikonfigurasi. Request ditolak.")
        return False

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
    tracker = LatencyTracker(message_id=msg_id, phone_number=phone_number)
    try:
        logger.info(f"Memproses pesan dari {phone_number}: '{message_text}' | Media: {media_id} | Session: {session}")

        # 1. Kirim tanda pesan dibaca (centang biru) & tampilkan animasi 'sedang mengetik...' di WA
        await whatsapp_service.send_seen(to_phone=phone_number, message_id=msg_id, session=session)
        await whatsapp_service.start_typing(to_phone=phone_number, session=session)

        # 2. Manajemen Sesi: Deteksi Kata Kunci Global Reset & Timeout 30 Menit
        should_reset, reset_reason, session_data = await SessionService.evaluate_incoming_message(
            phone_number=phone_number,
            message_text=message_text
        )

        if should_reset:
            welcome_intro = (
                "🌿 *Selamat Datang di TaniPintar Bot!*\n"
                "Asisten Sahabat Petani Cerdas untuk Perlindungan Tanaman Cabai & Padi.\n\n"
                "Silakan pilih menu layanan di bawah ini atau ketik pertanyaan Anda:"
            )
            if reset_reason == "session_timeout":
                welcome_intro = "⏱️ _Sesi sebelumnya telah berakhir karena tidak ada interaksi selama 30 menit._\n\n" + welcome_intro

            tracker.start_phase("waha_delivery")
            await whatsapp_service.send_text_message(to_phone=phone_number, text=welcome_intro, session=session)
            await asyncio.sleep(0.6)
            await whatsapp_service.send_main_menu_buttons(to_phone=phone_number, session=session)
            tracker.end_phase("waha_delivery")
            tracker.log_summary(has_media=bool(media_id))
            return

        # Ambil konteks tanaman terakhir dari sesi aktif jika tersedia
        last_crop = session_data.get("last_crop_context") if session_data else None

        # Jalankan LangGraph StateGraph dengan tracking latensi
        tracker.start_phase("pipeline_processing")
        initial_state = {
            "phone_number": phone_number,
            "user_message": message_text or "",
            "media_id": media_id,
            "media_url": None,
            "intent": "diagnosis",
            "crop_context": last_crop,
            "is_first_interaction": not bool(session_data),
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }

        result = await tani_graph_app.ainvoke(initial_state)
        tracker.end_phase("pipeline_processing")
        final_reply = result.get("final_response", "")

        detected_intent = result.get("intent", "diagnosis")

        if final_reply:
            # Jeda Alami (Human Typing Delay) untuk Anti-Ban Hygiene
            if settings.waha_human_delay_seconds > 0:
                await asyncio.sleep(settings.waha_human_delay_seconds)

            tracker.start_phase("waha_delivery")
            await whatsapp_service.send_text_message(to_phone=phone_number, text=final_reply, session=session)
            tracker.end_phase("waha_delivery")

            # 3. Pengiriman Komponen Interaktif Terstruktur
            clean_cmd = (message_text or "").lower().strip()
            if detected_intent == "greeting" or clean_cmd in ["menu", "bantuan", "mulai"]:
                # Kirim Menu Utama berbasis Tombol Interaktif (Interactive Buttons)
                await asyncio.sleep(0.6)
                await whatsapp_service.send_main_menu_buttons(to_phone=phone_number, session=session)

            elif detected_intent == "price_prompt":
                # Kirim Tombol Pilihan Komoditas Pasar
                await asyncio.sleep(0.6)
                await whatsapp_service.send_price_commodity_buttons(to_phone=phone_number, session=session)

            elif detected_intent in ["diagnosis", "vision_diagnosis"] and result.get("diagnosis_result"):
                # Kirim Reply Buttons (Tombol Pilihan Cepat) tindak lanjut perawatan
                await asyncio.sleep(0.6)
                await whatsapp_service.send_quick_action_buttons(
                    to_phone=phone_number,
                    body_text="Petani hebat, pilih langkah perawatan atau cek info terkait:",
                    context="diagnosis",
                    session=session
                )

        # Catat laporan latensi untuk demonstrasi dan evaluasi
        tracker.log_summary(has_media=bool(media_id))

    except Exception as e:
        logger.error(f"Gagal memproses pesan di background task: {e}", exc_info=True)
    finally:
        # 4. Hentikan animasi mengetik setelah pemrosesan selesai
        await whatsapp_service.stop_typing(to_phone=phone_number, session=session)


# Mapping Aksi Interaktif (ID Button / List Row -> Teks Query AI)
INTERACTIVE_ACTION_MAP = {
    # 4 Tombol Pilihan Cepat Menu Utama
    "btn_tanya_penyakit": "tanya penyakit",
    "btn_konsultasi_foto": "konsultasi foto",
    "btn_cek_harga": "cek harga pasar",
    "btn_info_cuaca": "info cuaca",

    # Tombol Pilihan Komoditas Cek Harga Pasar
    "btn_harga_cabai": "Berapa harga acuan cabai rawit merah hari ini?",
    "btn_harga_padi": "Berapa harga acuan gabah kering panen padi hari ini?",
    "btn_menu_utama": "menu",

    # Tindak Lanjut Diagnosa
    "btn_pupuk": "Rekomendasi takaran pupuk dan obat untuk penyakit ini.",
    "btn_cuaca": "Prakiraan cuaca dan waktu aman penyemprotan.",
    "btn_menu": "menu",

    # Kompatibilitas Menu List
    "menu_foto": "konsultasi foto",
    "menu_cabai": "Saya ingin konsultasi penyakit dan hama pada tanaman cabai.",
    "menu_padi": "Saya ingin konsultasi penyakit dan hama pada tanaman padi.",
    "menu_harga": "Berapa harga pasar cabai rawit dan gabah padi hari ini?",
    "menu_cuaca": "Bagaimana prakiraan cuaca dan waktu aman penyemprotan hari ini?",
    "menu_pupuk": "Rekomendasi takaran pupuk dan pencegahan hama tanaman.",
    "menu_riwayat": "riwayat"
}


@router.post("")
async def handle_whatsapp_event(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint penerima payload event dari WhatsApp Cloud API.
    Mendukung pesan teks, lampiran gambar, dan interaksi Button/List.
    """
    try:
        body = await request.json()

        entry = body.get("entry", [])
        if not entry:
            return {"status": "success", "message": "No entry found"}

        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "success", "message": "No changes found"}

        value = changes[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
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
        elif msg_type == "interactive":
            interactive = msg_obj.get("interactive", {})
            inter_type = interactive.get("type")
            if inter_type == "button_reply":
                btn_id = interactive.get("button_reply", {}).get("id", "")
                btn_title = interactive.get("button_reply", {}).get("title", "")
                extracted_text = INTERACTIVE_ACTION_MAP.get(btn_id) or btn_title or btn_id
            elif inter_type == "list_reply":
                list_id = interactive.get("list_reply", {}).get("id", "")
                list_title = interactive.get("list_reply", {}).get("title", "")
                extracted_text = INTERACTIVE_ACTION_MAP.get(list_id) or list_title or list_id
        elif msg_type == "image":
            image_obj = msg_obj.get("image", {})
            media_id = image_obj.get("id")
            extracted_text = image_obj.get("caption", "") or "Tolong diagnosa gejala penyakit tanaman pada foto ini."

        if sender_phone:
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
    Mendukung pesan teks, media, polling, Reply Buttons, dan List Message.
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

        # 4. Anti-Ban Filter
        if from_id.endswith("@g.us"):
            logger.info(f"[WAHA Webhook] Pesan grup diabaikan: {from_id}")
            return {"status": "success", "message": "Group messages ignored"}

        if from_id.endswith("@newsletter") or from_id == "status@broadcast":
            return {"status": "success", "message": "Channel or status broadcast ignored"}

        # 5. De-duplikasi pesan
        msg_id = payload.get("id")
        if msg_id and await message_deduplicator.is_duplicate_or_record(msg_id):
            logger.info(f"[WAHA Webhook] Pesan duplikat diabaikan: {msg_id}")
            return {"status": "success", "message": "Duplicate message ignored"}

        session_name = body.get("session") or settings.waha_session
        sender_phone = from_id

        # 6. Ekstraksi Teks (Teks Biasa, Reply Buttons, atau List Message Row)
        message_text = payload.get("body", "") or ""

        # Deteksi respons interaktif button reply
        selected_btn = (
            payload.get("selectedButtonId") or
            payload.get("buttonReply", {}).get("id") or
            payload.get("buttonReply", {}).get("title")
        )
        if selected_btn:
            message_text = INTERACTIVE_ACTION_MAP.get(selected_btn) or selected_btn

        # Deteksi respons interaktif list reply
        selected_row = (
            payload.get("selectedRowId") or
            payload.get("listReply", {}).get("id") or
            payload.get("listReply", {}).get("title")
        )
        if selected_row:
            message_text = INTERACTIVE_ACTION_MAP.get(selected_row) or selected_row

        # 7. Deteksi lampiran media
        media_id = None
        if payload.get("hasMedia"):
            media_obj = payload.get("media") or {}
            media_id = media_obj.get("url")
            if not media_id and msg_id:
                media_id = f"{settings.waha_base_url}/api/{session_name}/chats/{from_id}/messages/{msg_id}/media"

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


# ==============================================================
# Endpoint Test Interaktif (Buttons, List Message, & Poll)
# ==============================================================

@router.post("/test/send-buttons")
async def test_send_buttons(payload: dict):
    """
    Endpoint testing untuk mengirim Reply Buttons (Tombol Pilihan Cepat) ke nomor tujuan.
    Payload: {"phone": "628xxx", "body": "Pilih menu:", "buttons": [{"id": "btn_1", "text": "Pilihan 1"}]}
    """
    to_phone = payload.get("phone")
    if not to_phone:
        return Response(content=json.dumps({"status": "error", "message": "Field 'phone' wajib diisi"}), status_code=400)

    body = payload.get("body", "Silakan pilih salah satu opsi di bawah:")
    header = payload.get("header", "🌾 TaniPintar Pilihan Cepat")
    footer = payload.get("footer", "TaniPintar Asisten Pertanian")
    buttons = payload.get("buttons") or [
        {"id": "btn_cabai", "text": "🌶️ Cabai"},
        {"id": "btn_padi", "text": "🌾 Padi"},
        {"id": "btn_menu", "text": "📋 Menu Utama"}
    ]

    success = await whatsapp_service.send_buttons_message(
        to_phone=to_phone,
        body=body,
        buttons=buttons,
        header=header,
        footer=footer
    )
    return {
        "status": "success" if success else "error",
        "message": "Pesan Reply Buttons berhasil diproses" if success else "Gagal mengirim Reply Buttons"
    }


@router.post("/test/send-list")
async def test_send_list(payload: dict):
    """
    Endpoint testing untuk mengirim List Message (Menu Daftar) ke nomor tujuan.
    Payload: {"phone": "628xxx"}
    """
    to_phone = payload.get("phone")
    if not to_phone:
        return Response(content=json.dumps({"status": "error", "message": "Field 'phone' wajib diisi"}), status_code=400)

    success = await whatsapp_service.send_main_menu_list(to_phone=to_phone)
    return {
        "status": "success" if success else "error",
        "message": "List Message Menu Utama berhasil diproses" if success else "Gagal mengirim List Message"
    }


@router.post("/test/send-poll")
async def test_send_poll(payload: dict):
    """
    Endpoint testing untuk mengirim Poll WhatsApp ke nomor tujuan.
    Payload: {"phone": "628xxx", "question": "Tanaman apa yang sedang ditanam?", "options": ["Cabai", "Padi"]}
    """
    to_phone = payload.get("phone")
    if not to_phone:
        return Response(content=json.dumps({"status": "error", "message": "Field 'phone' wajib diisi"}), status_code=400)

    question = payload.get("question", "Apa komoditas utama lahan Anda?")
    options = payload.get("options") or ["Cabai Rawit", "Cabai Merah Keriting", "Padi Sawah", "Lainnya"]

    success = await whatsapp_service.send_poll_message(
        to_phone=to_phone,
        question=question,
        options=options
    )
    return {
        "status": "success" if success else "error",
        "message": "Poll WhatsApp berhasil diproses" if success else "Gagal mengirim Poll"
    }
