import httpx
from typing import Optional, Dict, Any
from core.config import settings
from core.logger import logger


class WhatsAppService:
    """Service untuk integrasi WhatsApp Cloud API resmi (Meta Graph API)."""

    def __init__(self):
        self.phone_number_id = settings.meta_wa_phone_number_id
        self.access_token = settings.meta_wa_access_token
        self.api_version = settings.meta_graph_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    async def send_text_message(self, to_phone: str, text: str, session: Optional[str] = None) -> bool:
        """Mengirim pesan teks ke nomor WhatsApp petani (Mendukung WAHA & Meta)."""
        if settings.whatsapp_provider == "waha":
            chat_id = to_phone if "@" in to_phone else f"{to_phone}@c.us"
            target_session = session or settings.waha_session
            waha_url = f"{settings.waha_base_url}/api/sendText"
            payload = {
                "session": target_session,
                "chatId": chat_id,
                "text": text
            }
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    res = await client.post(waha_url, json=payload)
                    if res.status_code in [200, 201]:
                        logger.info(f"Pesan WA (WAHA) berhasil dikirim ke {chat_id} (session: {target_session})")
                        return True
                    elif res.status_code == 422 and "does not exist" in res.text:
                        # Auto-discover session yang sedang WORKING
                        logger.warning(f"Session '{target_session}' tidak ditemukan di WAHA, mencari session yang aktif...")
                        sessions_res = await client.get(f"{settings.waha_base_url}/api/sessions")
                        if sessions_res.status_code == 200:
                            sessions_list = sessions_res.json()
                            for s in sessions_list:
                                if s.get("status") == "WORKING":
                                    fallback_session = s.get("name")
                                    payload["session"] = fallback_session
                                    retry_res = await client.post(waha_url, json=payload)
                                    if retry_res.status_code in [200, 201]:
                                        logger.info(f"Pesan WA (WAHA) berhasil dikirim ke {chat_id} via session aktif '{fallback_session}'")
                                        return True
                        logger.error(f"Gagal kirim WAHA: tidak ada session aktif yang ditemukan.")
                        return False
                    else:
                        logger.error(f"Gagal kirim WAHA (status {res.status_code}): {res.text}")
                        return False
            except Exception as e:
                logger.error(f"Error koneksi ke WAHA API ({settings.waha_base_url}): {e}")
                return False

        # Fallback ke Meta WhatsApp Cloud API
        if not self.access_token or not self.phone_number_id:
            logger.warning(f"[MOCK SEND WA] Ke {to_phone}: {text[:100]}... (Token Meta belum diisi)")
            return True

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {"preview_url": False, "body": text}
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in [200, 201]:
                    logger.info(f"Pesan WA berhasil dikirim ke {to_phone}")
                    return True
                else:
                    logger.error(f"Gagal kirim WA (status {res.status_code}): {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Error koneksi ke Meta Graph API: {e}")
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
                async with httpx.AsyncClient(timeout=30.0) as client:
                    media_res = await client.get(download_url)
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

