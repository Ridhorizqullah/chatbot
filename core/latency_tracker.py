import time
from typing import Dict, Optional, Any
from core.logger import logger


class LatencyTracker:
    """
    Tracker benchmark latensi dan running time pesan TaniPintar Bot.
    Mengukur waktu eksekusi langkah per langkah sesuai Slide 5 Dokumentasi Bimbingan:
      - T1: Webhook Ingestion
      - T2: Media Download & Storage Ingestion
      - T3: Vision Inference / Semantic RAG
      - T4: External Data Fetch (Weather Open-Meteo/BMKG & Market Price)
      - T5: LLM Reasoning & Text Formatting
      - T6: WAHA WhatsApp Delivery
    """

    def __init__(self, message_id: Optional[str] = None, phone_number: Optional[str] = None):
        self.message_id = message_id or "unknown"
        self.phone_number = phone_number or "unknown"
        self.start_time = time.perf_counter()
        self.checkpoints: Dict[str, float] = {}
        self.durations: Dict[str, float] = {}

    def start_phase(self, phase_name: str) -> None:
        """Menandai awal dari fase pemrosesan tertentu."""
        self.checkpoints[f"{phase_name}_start"] = time.perf_counter()

    def end_phase(self, phase_name: str) -> float:
        """Mengakhiri fase pemrosesan dan mencatat durasinya (dalam detik)."""
        now = time.perf_counter()
        start = self.checkpoints.get(f"{phase_name}_start", now)
        duration = now - start
        self.durations[phase_name] = duration
        return duration

    def get_total_duration(self) -> float:
        """Mengembalikan total waktu eksekusi end-to-end sejak inisialisasi."""
        return time.perf_counter() - self.start_time

    def log_summary(self, has_media: bool = False) -> Dict[str, Any]:
        """
        Menghasilkan ringkasan audit latensi dan mencetaknya ke structured logger.
        Sangat berguna untuk demonstrasi di depan dosen pembimbing.
        """
        total_rtt = self.get_total_duration()
        summary = {
            "message_id": self.message_id,
            "phone_number": self.phone_number,
            "is_multimodal": has_media,
            "total_rtt_seconds": round(total_rtt, 3),
            "total_rtt_ms": round(total_rtt * 1000, 1),
            "breakdown": {k: round(v, 3) for k, v in self.durations.items()}
        }

        t_breakdown = ", ".join([f"{k}: {v:.2f}s" for k, v in self.durations.items()])
        logger.info(
            f"⏱️ [LATENCY BENCHMARK] Total RTT: {total_rtt:.2f}s | "
            f"Mode: {'Multimodal (Foto+Teks)' if has_media else 'Teks'} | "
            f"Rincian: ({t_breakdown})"
        )
        return summary
