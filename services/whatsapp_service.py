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

    async def send_text_message(self, to_phone: str, text: str) -> bool:
        """Mengirim pesan teks ke nomor WhatsApp petani."""
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
        """Mengunduh file media (foto/audio) dari Meta Graph API berdasarkan media_id."""
        if not self.access_token:
            logger.warning("META_WA_ACCESS_TOKEN belum diset, tidak bisa mengunduh media.")
            return None

        # Langkah 1: Dapatkan URL unduh sementara dari media_id
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

                # Langkah 2: Unduh byte file sebenarnya
                media_res = await client.get(download_url, headers=headers)
                if media_res.status_code == 200:
                    return media_res.content
                else:
                    logger.error(f"Gagal mengunduh binary media: {media_res.status_code}")
                    return None
        except Exception as e:
            logger.error(f"Exception saat download media dari Meta: {e}")
            return None
