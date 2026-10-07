import time
import asyncio
from typing import Optional
from collections import OrderedDict
from core.config import settings
from core.logger import logger


class MessageDeDuplicator:
    """
    Manajer De-duplikasi pesan WhatsApp berstandar Enterprise.
    - Mencegah double-execution akibat retry network WAHA atau Meta Webhook.
    - Menggunakan algoritma O(1) TTL (Time-To-Live) dan kapasitas LRU terikat.
    - Mendukung distributed Redis jika REDIS_URL aktif, dengan fallback aman ke Local TTL Cache.
    """

    def __init__(self, ttl_seconds: int = 3600, max_size: int = 10000):
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, float] = OrderedDict()  # msg_id -> timestamp kadaluarsa
        self._redis = None
        self._init_redis()

    def _init_redis(self):
        """Mencoba inisialisasi koneksi Redis jika REDIS_URL tersedia."""
        if settings.redis_url:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
                logger.info(f"🚀 DeDuplicator berhasil terhubung ke distributed Redis: {settings.redis_url}")
            except ImportError:
                logger.debug("Library 'redis' belum terpasang, menggunakan In-Memory TTL Cache.")
            except Exception as e:
                logger.warning(f"Gagal menghubungkan ke Redis ({settings.redis_url}): {e}. Fallback ke In-Memory TTL Cache.")

    async def is_duplicate_or_record(self, msg_id: Optional[str]) -> bool:
        """
        Memeriksa status duplikasi pesan:
        - Jika pesan baru: mencatat ID pesan dan mengembalikan False (bukan duplikat).
        - Jika pesan sudah pernah tercatat dalam window TTL: mengembalikan True (duplikat).
        """
        if not msg_id:
            return False

        clean_id = str(msg_id).strip()
        if not clean_id:
            return False

        # 1. Jalur Distributed Redis (Multi-Worker / Multi-Replica Server)
        if self._redis:
            try:
                redis_key = f"tanipintar:wa_msg:{clean_id}"
                # SET key 1 NX EX ttl -> True jika key baru dibuat, None/False jika sudah ada
                is_created = await self._redis.set(redis_key, "1", ex=self.ttl_seconds, nx=True)
                return not bool(is_created)
            except Exception as e:
                logger.debug(f"Redis lookup error, fallback ke local TTL memory: {e}")

        # 2. Jalur In-Memory TTL LRU Cache (Thread-safe & Async-safe)
        async with self._lock:
            now = time.monotonic()

            # Bersihkan pesan kadaluarsa di awal antrean (FIFO)
            while self._cache and next(iter(self._cache.values())) <= now:
                self._cache.popitem(last=False)

            # Cek apakah ID sudah ada dan masih berlaku
            if clean_id in self._cache:
                expire_at = self._cache[clean_id]
                if expire_at > now:
                    return True
                else:
                    self._cache.pop(clean_id, None)

            # Eviksi item tertua jika batas kapasitas terlampaui
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            # Catat pesan baru
            self._cache[clean_id] = now + self.ttl_seconds
            return False

    async def clear(self):
        """Mengosongkan cache de-duplikasi (khusus pengujian)."""
        async with self._lock:
            self._cache.clear()


# Global Singleton DeDuplicator
message_deduplicator = MessageDeDuplicator()
