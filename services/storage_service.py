import uuid
from typing import Optional
from database.supabase_client import get_supabase
from core.config import settings
from core.logger import logger


class StorageService:
    """Service untuk mengarsipkan foto bukti fisik gejala tanaman ke Supabase Storage."""

    def __init__(self):
        self.bucket_name = settings.supabase_bucket_name

    async def upload_crop_symptom_photo(
        self,
        phone_number: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg"
    ) -> Optional[str]:
        """Mengunggah foto ke Supabase Storage bucket dan mengembalikan URL publik/aksesnya."""
        supabase = get_supabase()
        try:
            # Pastikan bucket ada atau gunakan bucket yang sudah dibuat
            file_extension = "jpg" if "jpeg" in content_type else "png"
            unique_filename = f"{phone_number}/{uuid.uuid4().hex}.{file_extension}"

            res = supabase.storage.from_(self.bucket_name).upload(
                path=unique_filename,
                file=image_bytes,
                file_options={"content-type": content_type}
            )

            # Dapatkan URL publik dari file yang baru diunggah
            public_url = supabase.storage.from_(self.bucket_name).get_public_url(unique_filename)
            logger.info(f"Foto gejala berhasil diarsipkan ke Supabase Storage: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Gagal mengunggah foto ke Supabase Storage: {e}")
            return None
