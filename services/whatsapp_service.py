import re
import httpx
from typing import Optional, Dict, Any, List
from core.config import settings
from core.logger import logger


def sanitize_chat_id(to_phone: str) -> str:
    """
    Menstandarkan Chat ID WhatsApp sesuai spesifikasi WAHA & Meta:
    - Jika sudah memiliki domain '@' (@c.us, @g.us, @lid), bersihkan whitespace dan pertahankan format.
    - Jika nomor telepon mentah (+62 812-3456-7890), hapus simbol non-digit dan format ke standard internasional (628...@c.us).
    """
    cleaned = str(to_phone).strip()
    if "@" in cleaned:
        return cleaned
    # Hapus semua karakter non-digit (+, -, spasi, tanda kurung)
    digits = re.sub(r"\D", "", cleaned)
    # Jika diawali awalan lokal '08', konversi ke prefix internasional Indonesia '628'
    if digits.startswith("08"):
        digits = "62" + digits[1:]
    return f"{digits}@c.us"


class WhatsAppService:
    """Service terpadu untuk integrasi WhatsApp via WAHA (WhatsApp HTTP API) & Meta Cloud API."""

    def __init__(self):
        self.phone_number_id = settings.meta_wa_phone_number_id
        self.access_token = settings.meta_wa_access_token
        self.api_version = settings.meta_graph_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def _get_waha_headers(self) -> Dict[str, str]:
        """Menyiapkan HTTP header untuk WAHA API, termasuk autentikasi X-Api-Key jika dikonfigurasi."""
        headers = {"Content-Type": "application/json"}
        if settings.waha_api_key:
            headers["X-Api-Key"] = settings.waha_api_key
        return headers

    async def send_text_message(
        self,
        to_phone: str,
        text: str,
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """Mengirim pesan teks ke nomor WhatsApp petani (Mendukung WAHA & Meta Cloud API, termasuk reply/quote message)."""
        chat_id = sanitize_chat_id(to_phone)

        if settings.whatsapp_provider == "waha":
            target_session = session or settings.waha_session
            waha_url = f"{settings.waha_base_url}/api/sendText"
            headers = self._get_waha_headers()
            payload: Dict[str, Any] = {
                "session": target_session,
                "chatId": chat_id,
                "text": text,
                "linkPreview": True
            }
            if reply_to:
                payload["reply_to"] = reply_to

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(waha_url, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        logger.info(f"Pesan WA (WAHA) berhasil dikirim ke {chat_id} (session: {target_session})")
                        return True
                    elif res.status_code == 422 and "does not exist" in res.text:
                        # Auto-discover session WAHA yang berstatus WORKING
                        logger.warning(f"Session '{target_session}' tidak ditemukan di WAHA, mencari session aktif...")
                        sessions_res = await client.get(f"{settings.waha_base_url}/api/sessions", headers=headers)
                        if sessions_res.status_code == 200:
                            sessions_list = sessions_res.json()
                            for s in sessions_list:
                                if s.get("status") == "WORKING":
                                    fallback_session = s.get("name")
                                    payload["session"] = fallback_session
                                    retry_res = await client.post(waha_url, json=payload, headers=headers)
                                    if retry_res.status_code in [200, 201]:
                                        logger.info(f"Pesan WA (WAHA) berhasil dikirim ke {chat_id} via session aktif '{fallback_session}'")
                                        return True
                        logger.error("Gagal kirim WAHA: tidak ada session aktif yang ditemukan.")
                        return False
                    else:
                        logger.error(f"Gagal kirim WAHA (status {res.status_code}): {res.text}")
                        return False
            except Exception as e:
                logger.error(f"Error koneksi ke WAHA API ({settings.waha_base_url}): {e}")
                return False

        # Fallback ke Meta WhatsApp Cloud API resmi
        if not self.access_token or not self.phone_number_id:
            logger.warning(f"[MOCK SEND WA] Ke {chat_id}: {text[:100]}... (Token Meta belum diisi)")
            return True

        # Format nomor untuk Meta Cloud API (hanya angka tanpa @c.us)
        meta_recipient = chat_id.replace("@c.us", "").replace("@s.whatsapp.net", "")
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": meta_recipient,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }
        if reply_to:
            payload["context"] = {"message_id": reply_to}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in [200, 201]:
                    logger.info(f"Pesan WA (Meta Cloud) berhasil dikirim ke {meta_recipient}")
                    return True
                else:
                    logger.error(f"Gagal kirim WA Meta (status {res.status_code}): {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Error koneksi ke Meta Graph API: {e}")
            return False

    async def send_buttons_message(
        self,
        to_phone: str,
        body: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Mengirim pesan Reply Buttons (Tombol Pilihan Cepat) interaktif.
        Mendukung WAHA (/api/sendButtons) dan Meta WhatsApp Cloud API (interactive button).
        
        Format buttons parameter:
        [
            {"id": "btn_cabai", "text": "Cabai"},
            {"id": "btn_padi", "text": "Padi"}
        ]
        Maksimal 3-4 tombol. Jika gagal/tidak didukung, otomatis fallback ke pesan teks bernomor.
        Mendukung reply_to untuk me-quote pesan pengguna secara langsung.
        """
        chat_id = sanitize_chat_id(to_phone)
        footer_text = footer or "TaniPintar Asisten Pertanian"

        # 1. Implementasi untuk WAHA
        if settings.whatsapp_provider == "waha":
            target_session = session or settings.waha_session
            url = f"{settings.waha_base_url}/api/sendButtons"
            headers = self._get_waha_headers()

            # Format tombol sesuai skema WAHA (ButtonType: reply)
            waha_buttons = []
            for b in buttons[:4]:  # Batasi maks 4 tombol
                btn_id = b.get("id") or b.get("text", "")
                btn_text = b.get("text", "")[:20]
                waha_buttons.append({
                    "type": "reply",
                    "text": btn_text,
                    "id": btn_id
                })

            payload: Dict[str, Any] = {
                "session": target_session,
                "chatId": chat_id,
                "body": body,
                "footer": footer_text,
                "buttons": waha_buttons
            }
            if header:
                payload["header"] = header
            if reply_to:
                payload["reply_to"] = reply_to

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        logger.info(f"[WAHA] Reply Buttons berhasil dikirim ke {chat_id}")
                        return True
                    else:
                        logger.warning(f"[WAHA] Gagal kirim Buttons (status {res.status_code}): {res.text}. Melakukan fallback ke teks biasa...")
            except Exception as e:
                logger.warning(f"[WAHA] Exception kirim buttons ke {chat_id}: {e}. Fallback ke teks biasa.")

        # 2. Implementasi untuk Meta WhatsApp Cloud API
        elif self.access_token and self.phone_number_id:
            meta_recipient = chat_id.replace("@c.us", "").replace("@s.whatsapp.net", "")
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            meta_buttons = []
            for b in buttons[:3]:  # Meta membatasi maks 3 tombol quick reply
                btn_id = b.get("id") or b.get("text", "")
                btn_text = b.get("text", "")[:20]
                meta_buttons.append({
                    "type": "reply",
                    "reply": {
                        "id": btn_id,
                        "title": btn_text
                    }
                })

            interactive_payload: Dict[str, Any] = {
                "type": "button",
                "body": {"text": body},
                "footer": {"text": footer_text},
                "action": {"buttons": meta_buttons}
            }
            if header:
                interactive_payload["header"] = {"type": "text", "text": header}

            payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": meta_recipient,
                "type": "interactive",
                "interactive": interactive_payload
            }
            if reply_to:
                payload["context"] = {"message_id": reply_to}

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code in [200, 201]:
                        logger.info(f"[Meta] Reply Buttons berhasil dikirim ke {meta_recipient}")
                        return True
                    else:
                        logger.warning(f"[Meta] Gagal kirim interactive buttons: {res.text}. Fallback ke teks...")
            except Exception as e:
                logger.warning(f"[Meta] Exception interactive buttons: {e}. Fallback ke teks...")

        # 3. Fallback Elegan: Teks Bernomor jika interactive buttons tidak didukung
        options_text = "\n".join([f"👉 *{i+1}.* {b.get('text')}" for i, b in enumerate(buttons)])
        hint_footer = f"TaniPintar • Balas dengan angka 1 - {len(buttons)} atau ketik pilihan Anda"
        fallback_msg = f"{header + chr(10) + chr(10) if header else ''}{body}\n\n*Pilihan Cepat:*\n{options_text}\n\n_{hint_footer}_"
        return await self.send_text_message(to_phone=to_phone, text=fallback_msg, session=session, reply_to=reply_to)

    async def send_list_message(
        self,
        to_phone: str,
        title: str,
        description: str,
        button_text: str,
        sections: List[Dict[str, Any]],
        footer: Optional[str] = None,
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Mengirim pesan List Message (Menu Daftar) interaktif dengan kategori (Sections) dan baris pilihan (Rows).
        Mendukung WAHA (/api/sendList) dan Meta WhatsApp Cloud API (interactive list).
        
        Format sections:
        [
            {
                "title": "Konsultasi Tanaman",
                "rows": [
                    {"rowId": "menu_cabai", "title": "Cabai", "description": "Diagnosa tanaman cabai"},
                    {"rowId": "menu_padi", "title": "Padi", "description": "Diagnosa tanaman padi"}
                ]
            }
        ]
        """
        chat_id = sanitize_chat_id(to_phone)
        footer_text = footer or "TaniPintar Asisten Pertanian"

        # 1. Implementasi untuk WAHA
        if settings.whatsapp_provider == "waha":
            target_session = session or settings.waha_session
            url = f"{settings.waha_base_url}/api/sendList"
            headers = self._get_waha_headers()

            payload: Dict[str, Any] = {
                "session": target_session,
                "chatId": chat_id,
                "message": {
                    "title": title,
                    "description": description,
                    "button": button_text[:20],
                    "footer": footer_text,
                    "sections": sections
                }
            }
            if reply_to:
                payload["reply_to"] = reply_to

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        logger.info(f"[WAHA] List Message berhasil dikirim ke {chat_id}")
                        return True
                    else:
                        logger.warning(f"[WAHA] Gagal kirim List Message (status {res.status_code}): {res.text}. Fallback ke format teks...")
            except Exception as e:
                logger.warning(f"[WAHA] Exception sendList ke {chat_id}: {e}. Fallback ke format teks.")

        # 2. Implementasi untuk Meta WhatsApp Cloud API
        elif self.access_token and self.phone_number_id:
            meta_recipient = chat_id.replace("@c.us", "").replace("@s.whatsapp.net", "")
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            # Sesuaikan format rows Meta: rowId -> id
            meta_sections = []
            for sec in sections:
                meta_rows = []
                for r in sec.get("rows", []):
                    row_dict = {
                        "id": r.get("rowId") or r.get("id", ""),
                        "title": r.get("title", "")[:24]
                    }
                    if r.get("description"):
                        row_dict["description"] = r.get("description", "")[:72]
                    meta_rows.append(row_dict)
                meta_sections.append({
                    "title": sec.get("title", "")[:24],
                    "rows": meta_rows
                })

            payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": meta_recipient,
                "type": "interactive",
                "interactive": {
                    "type": "list",
                    "header": {"type": "text", "text": title[:60]},
                    "body": {"text": description},
                    "footer": {"text": footer_text[:60]},
                    "action": {
                        "button": button_text[:20],
                        "sections": meta_sections
                    }
                }
            }
            if reply_to:
                payload["context"] = {"message_id": reply_to}

            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code in [200, 201]:
                        logger.info(f"[Meta] List Message berhasil dikirim ke {meta_recipient}")
                        return True
                    else:
                        logger.warning(f"[Meta] Gagal kirim interactive list: {res.text}. Fallback ke teks...")
            except Exception as e:
                logger.warning(f"[Meta] Exception interactive list: {e}. Fallback ke teks...")

        # 3. Fallback Elegan: Teks Terstruktur dengan Nomor Menu
        text_lines = [f"📋 *{title}*", f"{description}\n"]
        counter = 1
        for sec in sections:
            text_lines.append(f"📌 *{sec.get('title', 'Menu')}:*")
            for r in sec.get("rows", []):
                desc_str = f" - _{r.get('description')}_" if r.get('description') else ""
                text_lines.append(f"  *{counter}.* {r.get('title')}{desc_str}")
                counter += 1
            text_lines.append("")
        text_lines.append(f"_{footer_text}_")
        fallback_msg = "\n".join(text_lines)
        return await self.send_text_message(to_phone=to_phone, text=fallback_msg, session=session, reply_to=reply_to)

    async def send_poll_message(
        self,
        to_phone: str,
        question: str,
        options: List[str],
        multiple_answers: bool = False,
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Mengirim pesan Poll WhatsApp via WAHA (/api/sendPoll) sebagai alternatif interaktif paling tangguh.
        Sangat direkomendasikan pada engine GOWS/NOWEB karena bekerja konsisten di seluruh versi WhatsApp.
        """
        chat_id = sanitize_chat_id(to_phone)
        if settings.whatsapp_provider == "waha":
            target_session = session or settings.waha_session
            url = f"{settings.waha_base_url}/api/sendPoll"
            headers = self._get_waha_headers()
            payload: Dict[str, Any] = {
                "session": target_session,
                "chatId": chat_id,
                "poll": {
                    "name": question,
                    "options": options[:12],
                    "multipleAnswers": multiple_answers
                }
            }
            if reply_to:
                payload["reply_to"] = reply_to

            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code in [200, 201]:
                        logger.info(f"[WAHA] Poll berhasil dikirim ke {chat_id}")
                        return True
                    else:
                        logger.warning(f"[WAHA] Gagal kirim Poll: {res.text}")
            except Exception as e:
                logger.error(f"[WAHA] Error kirim poll ke {chat_id}: {e}")

        # Fallback ke format teks pilihan jika provider bukan WAHA atau polling gagal
        options_text = "\n".join([f"🔘 {opt}" for opt in options])
        fallback_msg = f"📊 *{question}*\n\n{options_text}\n\n_Ketik salah satu pilihan di atas untuk menjawab._"
        return await self.send_text_message(to_phone=to_phone, text=fallback_msg, session=session, reply_to=reply_to)

    async def send_main_menu_list(
        self,
        to_phone: str,
        session: Optional[str] = None,
        reply_to: Optional[str] = None,
        prefix_notice: Optional[str] = None
    ) -> bool:
        """
        Helper spesifik TaniPintar: Mengirimkan List Message Menu Utama untuk 6 Layanan Pertanian
        melalui endpoint WAHA /api/sendList (1 section 'Layanan TaniPintar' dengan 6 baris pilihan).
        """
        sections = [
            {
                "title": "Layanan TaniPintar",
                "rows": [
                    {
                        "rowId": "btn_tanya_penyakit",
                        "title": "Tanya Hama & Penyakit",
                        "description": "Ceritakan gejala tanaman lewat teks"
                    },
                    {
                        "rowId": "btn_konsultasi_foto",
                        "title": "Konsultasi Foto",
                        "description": "Kirim foto daun/buah untuk dianalisis"
                    },
                    {
                        "rowId": "btn_cek_harga",
                        "title": "Cek Harga Pasar",
                        "description": "Harga cabai & padi hari ini"
                    },
                    {
                        "rowId": "btn_info_cuaca",
                        "title": "Info Cuaca & Semprot",
                        "description": "Waktu aman penyemprotan di lokasimu"
                    },
                    {
                        "rowId": "btn_pupuk",
                        "title": "Panduan Pupuk & Obat",
                        "description": "Dosis pupuk dan pestisida"
                    },
                    {
                        "rowId": "btn_riwayat",
                        "title": "Riwayat Konsultasi",
                        "description": "Lihat konsultasi sebelumnya"
                    }
                ]
            }
        ]

        base_desc = (
            "🌿 *Selamat Datang di TaniPintar!*\n"
            "Asisten Sahabat Petani Cerdas untuk Perlindungan Tanaman Cabai & Padi.\n\n"
            "Silakan pilih menu layanan di bawah ini atau balas dengan angka 1 - 6:"
        )
        description = f"{prefix_notice.strip()}\n\n{base_desc}" if prefix_notice else base_desc

        return await self.send_list_message(
            to_phone=to_phone,
            title="🌾 Menu Layanan TaniPintar",
            description=description,
            button_text="Pilih Layanan",
            sections=sections,
            footer="TaniPintar • Sahabat Petani Cerdas",
            session=session,
            reply_to=reply_to
        )

    async def send_welcome_menu(
        self,
        to_phone: str,
        session: Optional[str] = None,
        reply_to: Optional[str] = None,
        prefix_notice: Optional[str] = None
    ) -> bool:
        """
        Fungsi Utama Kirim Pesan Sambutan + WhatsApp List Message Utama (Single Message Flow):
        Mengirimkan menu interaktif 6 layanan TaniPintar via WAHA /api/sendList.
        Mendukung parameter reply_to untuk me-quote pesan pengguna dan prefix_notice jika ada timeout sesi.
        """
        return await self.send_main_menu_list(
            to_phone=to_phone,
            session=session,
            reply_to=reply_to,
            prefix_notice=prefix_notice
        )

    async def send_main_menu_buttons(
        self,
        to_phone: str,
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Mengirimkan Menu Utama interaktif TaniPintar.
        Mendelegasikan ke send_welcome_menu untuk menjamin keseragaman tampilan menu utama 6 layanan.
        """
        return await self.send_welcome_menu(to_phone=to_phone, session=session, reply_to=reply_to)

    async def send_price_commodity_buttons(
        self,
        to_phone: str,
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Mengirimkan tombol/list interaktif untuk mengarahkan petani memilih komoditas pasar (Cabai vs Padi/Beras).
        Untuk WAHA (GOWS engine), menggunakan List Message interaktif yang memiliki tombol klik nyata.
        """
        buttons = [
            {"id": "btn_harga_cabai", "text": "🌶️ Cabai (Rawit/Merah)"},
            {"id": "btn_harga_padi", "text": "🌾 Padi & Beras (GKP/Beras)"},
            {"id": "btn_menu_utama", "text": "📋 Menu Utama"}
        ]
        if settings.whatsapp_provider == "waha":
            sections = [
                {
                    "title": "Pilihan Komoditas",
                    "rows": [
                        {
                            "rowId": "btn_harga_cabai",
                            "title": "🌶️ Cabai",
                            "description": "Rawit Merah, Hijau, Keriting, Besar"
                        },
                        {
                            "rowId": "btn_harga_padi",
                            "title": "🌾 Padi & Beras",
                            "description": "Gabah GKP, Beras Medium & Super"
                        },
                        {
                            "rowId": "btn_menu_utama",
                            "title": "📋 Menu Utama",
                            "description": "Kembali ke 6 menu layanan"
                        }
                    ]
                }
            ]
            return await self.send_list_message(
                to_phone=to_phone,
                title="📊 Info Harga Pasar",
                description="💰 *PILIHAN KOMODITAS HARGA PASAR*\n\nSilakan pilih komoditas yang ingin Anda cek harga acuannya di D.I. Yogyakarta & Magelang:",
                button_text="Pilih Komoditas",
                sections=sections,
                footer="TaniPintar • Data Pasar Harian",
                session=session,
                reply_to=reply_to
            )

        return await self.send_buttons_message(
            to_phone=to_phone,
            body="💰 *PILIHAN KOMODITAS HARGA PASAR*\n\nSilakan pilih komoditas yang ingin Anda cek harga acuannya di D.I. Yogyakarta & Magelang:",
            buttons=buttons,
            header="📊 Info Harga Pasar",
            footer="TaniPintar • Data Pasar Harian",
            session=session,
            reply_to=reply_to
        )

    async def send_price_region_list(
        self,
        to_phone: str,
        commodity_label: str = "Cabai",
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Mengirimkan daftar pilihan wilayah pasar sentra untuk cek harga komoditas terpilih.
        Menggunakan List Message interaktif untuk WAHA (GOWS engine).
        """
        regions = [
            {"id": "btn_region_sleman", "title": "Sleman (DIY)", "desc": "Titik Kumpul Tempel & Pasar Godean"},
            {"id": "btn_region_bantul", "title": "Bantul (DIY)", "desc": "Pasar Niten & Pasar Imogiri"},
            {"id": "btn_region_kulonprogo", "title": "Kulon Progo (DIY)", "desc": "Pasar Lelang Garongan/Bugel & Wates"},
            {"id": "btn_region_jogja", "title": "Kota Yogyakarta", "desc": "Pasar Induk Giwangan & Beringharjo"},
            {"id": "btn_region_magelang", "title": "Magelang & Muntilan", "desc": "Pasar Rejowinangun & Lelang Sayur"},
        ]
        if settings.whatsapp_provider == "waha":
            sections = [
                {
                    "title": f"Wilayah Pasar ({commodity_label})",
                    "rows": [
                        {
                            "rowId": r["id"],
                            "title": r["title"][:24],
                            "description": r["desc"][:72]
                        }
                        for r in regions
                    ]
                }
            ]
            return await self.send_list_message(
                to_phone=to_phone,
                title="📍 Wilayah Pasar",
                description=(
                    f"📍 *PILIH WILAYAH PASAR ({commodity_label.upper()})*\n\n"
                    f"Silakan pilih wilayah sentra pasar yang ingin Anda pantau harganya:"
                ),
                button_text="Pilih Wilayah",
                sections=sections,
                footer="TaniPintar • Acuan Pasar DIY & Magelang",
                session=session,
                reply_to=reply_to
            )

        buttons = [
            {"id": r["id"], "text": r["title"][:20]}
            for r in regions[:3]
        ]
        return await self.send_buttons_message(
            to_phone=to_phone,
            body=f"📍 *PILIH WILAYAH PASAR ({commodity_label.upper()})*\n\nSilakan pilih wilayah sentra pasar:",
            buttons=buttons,
            header="📍 Wilayah Pasar",
            footer="TaniPintar • Acuan Pasar DIY & Magelang",
            session=session,
            reply_to=reply_to
        )

    async def send_quick_action_buttons(
        self,
        to_phone: str,
        body_text: str,
        context: str = "diagnosis",
        session: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> bool:
        """
        Helper spesifik TaniPintar: Mengirimkan tombol interaktif tindak lanjut.
        Untuk WAHA (GOWS engine), menggunakan List Message interaktif yang memiliki tombol klik nyata.
        """
        if context == "diagnosis":
            buttons = [
                {"id": "btn_pupuk", "text": "🧪 Dosis Pupuk & Obat"},
                {"id": "btn_cuaca", "text": "🌦️ Waktu Aman Semprot"},
                {"id": "btn_menu", "text": "📋 Menu Utama"}
            ]
            header = "💡 Tindak Lanjut Diagnosa"
        elif context == "price":
            buttons = [
                {"id": "btn_cabai", "text": "🌶️ Cek Penyakit Cabai"},
                {"id": "btn_padi", "text": "🌾 Cek Penyakit Padi"},
                {"id": "btn_menu", "text": "📋 Menu Utama"}
            ]
            header = "📊 Pilihan Layanan Lain"
        else:
            buttons = [
                {"id": "btn_cabai", "text": "🌶️ Cabai"},
                {"id": "btn_padi", "text": "🌾 Padi"},
                {"id": "btn_menu", "text": "📋 Menu Utama"}
            ]
            header = "🌾 TaniPintar Bot"

        if settings.whatsapp_provider == "waha":
            sections = [
                {
                    "title": header,
                    "rows": [
                        {
                            "rowId": b["id"],
                            "title": b["text"],
                            "description": "Pilih untuk lanjut"
                        }
                        for b in buttons
                    ]
                }
            ]
            return await self.send_list_message(
                to_phone=to_phone,
                title=header,
                description=body_text,
                button_text="Pilih Tindak Lanjut",
                sections=sections,
                footer="TaniPintar • Sahabat Petani Cerdas",
                session=session,
                reply_to=reply_to
            )

        return await self.send_buttons_message(
            to_phone=to_phone,
            body=body_text,
            buttons=buttons,
            header=header,
            footer="TaniPintar • Pilihan Tindak Lanjut",
            session=session,
            reply_to=reply_to
        )

    async def start_typing(self, to_phone: str, session: Optional[str] = None) -> bool:
        """
        Menampilkan animasi 'sedang mengetik...' (typing presence) di WhatsApp petani.
        Dipanggil sebelum proses AI/RAG/Vision agar pengguna mengetahui bot sedang memproses.
        Mendukung endpoint WAHA /api/startTyping, /api/presence, dan fallback ke /api/{session}/presence.
        """
        if settings.whatsapp_provider == "waha":
            chat_id = sanitize_chat_id(to_phone)
            target_session = session or settings.waha_session
            headers = self._get_waha_headers()

            # 1. Coba endpoint WAHA /api/startTyping
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        f"{settings.waha_base_url}/api/startTyping",
                        json={"session": target_session, "chatId": chat_id},
                        headers=headers
                    )
                    if res.status_code in [200, 201]:
                        return True
            except Exception as e:
                logger.debug(f"Percobaan panggil /api/startTyping: {e}")

            # 2. Coba endpoint WAHA /api/presence
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        f"{settings.waha_base_url}/api/presence",
                        json={"session": target_session, "chatId": chat_id, "presence": "typing"},
                        headers=headers
                    )
                    if res.status_code in [200, 201]:
                        return True
            except Exception as e:
                logger.debug(f"Percobaan panggil /api/presence: {e}")

            # 3. Fallback ke endpoint session presence /api/{session}/presence
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        f"{settings.waha_base_url}/api/{target_session}/presence",
                        json={"chatId": chat_id, "presence": "typing"},
                        headers=headers
                    )
                    return res.status_code in [200, 201]
            except Exception as e:
                logger.debug(f"Gagal set status typing di WAHA: {e}")
                return False
        return False

    async def stop_typing(self, to_phone: str, session: Optional[str] = None) -> bool:
        """
        Menghentikan animasi 'sedang mengetik...' dan mengembalikan status ke paused.
        Mendukung endpoint WAHA /api/stopTyping, /api/presence, dan fallback ke /api/{session}/presence.
        """
        if settings.whatsapp_provider == "waha":
            chat_id = sanitize_chat_id(to_phone)
            target_session = session or settings.waha_session
            headers = self._get_waha_headers()

            # 1. Coba endpoint WAHA /api/stopTyping
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        f"{settings.waha_base_url}/api/stopTyping",
                        json={"session": target_session, "chatId": chat_id},
                        headers=headers
                    )
                    if res.status_code in [200, 201]:
                        return True
            except Exception as e:
                logger.debug(f"Percobaan panggil /api/stopTyping: {e}")

            # 2. Coba endpoint WAHA /api/presence
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        f"{settings.waha_base_url}/api/presence",
                        json={"session": target_session, "chatId": chat_id, "presence": "paused"},
                        headers=headers
                    )
                    if res.status_code in [200, 201]:
                        return True
            except Exception as e:
                logger.debug(f"Percobaan panggil /api/presence: {e}")

            # 3. Fallback ke endpoint session presence /api/{session}/presence
            try:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    res = await client.post(
                        f"{settings.waha_base_url}/api/{target_session}/presence",
                        json={"chatId": chat_id, "presence": "paused"},
                        headers=headers
                    )
                    return res.status_code in [200, 201]
            except Exception as e:
                logger.debug(f"Gagal set status paused di WAHA: {e}")
                return False
        return False

    async def send_seen(self, to_phone: str, message_id: Optional[str] = None, session: Optional[str] = None) -> bool:
        """Mengirimkan tanda centang biru (telah dibaca / seen) ke WhatsApp petani."""
        if settings.whatsapp_provider == "waha":
            chat_id = sanitize_chat_id(to_phone)
            target_session = session or settings.waha_session
            url = f"{settings.waha_base_url}/api/sendSeen"
            payload = {
                "session": target_session,
                "chatId": chat_id,
            }
            if message_id:
                payload["messageIds"] = [message_id]
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.post(url, json=payload, headers=self._get_waha_headers())
                    return res.status_code in [200, 201]
            except Exception as e:
                logger.debug(f"Gagal kirim sendSeen di WAHA: {e}")
                return False
        return False

    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Mengunduh file media (foto/audio) dari WAHA atau Meta Graph API berdasarkan media_id / URL."""
        if not media_id:
            return None

        # Kasus 1: Media berupa URL (WAHA atau direct HTTP)
        if media_id.startswith("http://") or media_id.startswith("https://") or media_id.startswith("/"):
            download_url = media_id
            # Ganti localhost/127.0.0.1 dengan waha_base_url agar bisa diakses antar-kontainer Docker
            if "localhost:3000" in download_url:
                download_url = download_url.replace("http://localhost:3000", settings.waha_base_url).replace("https://localhost:3000", settings.waha_base_url)
            elif "127.0.0.1:3000" in download_url:
                download_url = download_url.replace("http://127.0.0.1:3000", settings.waha_base_url).replace("https://127.0.0.1:3000", settings.waha_base_url)
            elif download_url.startswith("/"):
                download_url = f"{settings.waha_base_url}{download_url}"

            try:
                headers = self._get_waha_headers() if settings.waha_base_url in download_url else {}
                async with httpx.AsyncClient(timeout=30.0) as client:
                    media_res = await client.get(download_url, headers=headers)
                    if media_res.status_code == 200:
                        logger.info(f"Berhasil mengunduh media dari WAHA: {download_url} ({len(media_res.content)} bytes)")
                        return media_res.content
                    else:
                        logger.error(f"Gagal mengunduh media dari WAHA ({media_res.status_code}): {media_res.text}")
                        return None
            except Exception as e:
                logger.error(f"Exception saat download media dari WAHA: {e}")
                return None

        # Kasus 2: Meta Graph API (ID numerik media)
        if not self.access_token:
            logger.warning("META_WA_ACCESS_TOKEN belum diset, tidak bisa mengunduh media dari Meta.")
            return None

        meta_url = f"{self.base_url}/{media_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(meta_url, headers=headers)
                if res.status_code != 200:
                    logger.error(f"Gagal mendapatkan media URL dari Meta: {res.text}")
                    return None
                data = res.json()
                download_url = data.get("url")

                if not download_url:
                    return None

                media_res = await client.get(download_url, headers=headers)
                if media_res.status_code == 200:
                    return media_res.content
                else:
                    logger.error(f"Gagal mengunduh binary media dari Meta: {media_res.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Exception saat download media dari Meta: {e}")
            return None


# Singleton instance WhatsAppService
whatsapp_service = WhatsAppService()
