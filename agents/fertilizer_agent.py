from typing import Optional
from google import genai
from core.config import settings
from core.logger import logger
from agents.schemas import FertilizerRecommendationResult


import json
import os
from typing import Optional, Dict, Any
from google import genai
from core.config import settings
from core.logger import logger
from agents.schemas import FertilizerRecommendationResult


class FertilizerAgent:
    """Agent penghitung dan perekomendasi pupuk & pestisida spesifik untuk Cabai dan Padi."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        """Memuat dataset katalog pupuk dan pestisida berimbang dari file JSON."""
        catalog_path = os.path.join(
            os.path.dirname(__file__), "..", "data", "knowledge", "fertilizer_pesticide_catalog.json"
        )
        try:
            if os.path.exists(catalog_path):
                with open(catalog_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Gagal memuat katalog pupuk dari {catalog_path}: {e}")
        return {}

    def get_recommendation(self, query: str, crop_hint: Optional[str] = None) -> FertilizerRecommendationResult:
        """Menghasilkan rekomendasi pupuk dan pestisida terstruktur berdasarkan pertanyaan petani."""
        q_lower = query.lower()
        crop = "padi" if (crop_hint and "padi" in crop_hint.lower()) or ("padi" in q_lower or "gabah" in q_lower or "sawah" in q_lower or "beras" in q_lower) else "cabai"

        # Identifikasi fase tanaman spesifik berbasis aturan linguistik agronomi
        if crop == "cabai":
            if any(w in q_lower for w in ["bibit", "semai", "persemaian", "pindah tanam", "polybag", "0 hst", "10 hst", "15 hst"]):
                fase_key = "fase_bibit"
            elif any(w in q_lower for w in ["bunga", "rontok bunga", "pentil", "bakal buah", "kuncup", "mekar"]):
                fase_key = "fase_bunga"
            elif any(w in q_lower for w in ["buah", "panen", "matang", "petik", "merah", "bobot", "patek", "busuk buah"]):
                fase_key = "fase_buah"
            else:
                fase_key = "fase_vegetatif"
        else:
            # Padi
            if any(w in q_lower for w in ["benih", "semai", "persemaian", "olah tanah", "dasar", "singkal", "keong"]):
                fase_key = "fase_persemaian"
            elif any(w in q_lower for w in ["bunting", "primordia", "kebuntingan", "leher", "malai keluar", "blas leher", "35 hst", "45 hst"]):
                fase_key = "fase_bunting"
            elif any(w in q_lower for w in ["panen", "bernas", "gabah", "pengisian", "merunduk", "kuning", "walang sangit", "wbc"]):
                fase_key = "fase_malai_panen"
            else:
                fase_key = "fase_vegetatif"

        # Ambil data agronomi dari katalog
        crop_data = self.catalog.get(crop, {})
        phase_data = crop_data.get(fase_key, {})

        fase_display = phase_data.get("rentang_hst", fase_key.replace("_", " ").title())
        unsur = phase_data.get("unsur_prioritas", "Nutrisi makro N-P-K berimbang dan mikro")
        rekomendasi = phase_data.get("rekomendasi_pupuk", [
            "NPK 16-16-16 dosis anjuran kocor pada pagi hari.",
            "Asam humat untuk pembenah tanah dan perakaran.",
            "Pupuk daun mikro semprot interval 7-10 hari."
        ])

        pht_info = phase_data.get("pestisida_dan_pht", {})
        pestisida_text = (
            f"🌱 *Pilihan Hayati/Organik:* {pht_info.get('organik_hayati', '-')}\n"
            f"🛡️ *Rotasi Kimiawi Terdaftar:* {pht_info.get('kimia_rotasi', '-')}\n"
            f"⚠️ *Panduan MoA / Resistensi:* {pht_info.get('anjuran_rotasi', '-')}"
        )
        aplikasi = phase_data.get("catatan_aplikasi", "Aplikasi pagi hari saat tanah lembap. Perhatikan arah angin saat penyemprotan.")

        if not self.client:
            return FertilizerRecommendationResult(
                nama_tanaman=crop,
                fase_pertumbuhan=fase_display,
                rekomendasi_pupuk=rekomendasi,
                unsur_prioritas=unsur,
                pestisida_pendamping=pestisida_text,
                catatan_aplikasi=aplikasi
            )

        prompt = f"""\
Anda adalah pakar nutrisi tanaman pangan dan hortikultura di Indonesia.
Petani bertanya seputar pupuk/pestisida: "{query}"
Target Tanaman: {crop.upper()}
Fase Pertumbuhan Terdeteksi: {fase_display}

Panduan Standar Agronomi Resmi (Katalog PHT Kementan):
- Unsur Prioritas: {unsur}
- Opsi Pupuk: {rekomendasi}
- Proteksi Tanaman (PHT Hayati & Kimia Terdaftar):
  * Hayati: {pht_info.get('organik_hayati')}
  * Kimia Rotasi: {pht_info.get('kimia_rotasi')}
  * MoA/Resistensi: {pht_info.get('anjuran_rotasi')}
- Cara Aplikasi: {aplikasi}

PETUNJUK KHUSUS (NON-TEMPLATE & BERIMBANG):
1. Sesuaikan jawaban dengan fokus pertanyaan petani. JANGAN copy-paste mentah tanpa konteks.
2. Selalu seimbangkan opsi agens hayati (Trichoderma/Beauveria/PGPR) dan opsi bahan aktif kimiawi.
3. Cantumkan takaran aplikatif yang jelas (misal: per tangki semprot standar 16 Liter, atau per drum 200 Liter).
4. Tekankan rotasi bahan aktif (MoA / FRAC / IRAC) agar hama/patogen tidak resisten.
5. Kembalikan dalam format JSON terstruktur skema FertilizerRecommendationResult.
"""
        candidate_models = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]
        if self.model_name and self.model_name.replace("models/", "") not in candidate_models:
            candidate_models.append(self.model_name.replace("models/", ""))
        for m in ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.8-flash"]:
            if m not in candidate_models:
                candidate_models.append(m)

        for model in candidate_models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": FertilizerRecommendationResult,
                        "temperature": 0.2,
                    }
                )
                if response.parsed:
                    return response.parsed
            except Exception as e:
                logger.warning(f"Percobaan model pupuk '{model}' gagal: {e}. Mencoba model cadangan...")

        return FertilizerRecommendationResult(
            nama_tanaman=crop,
            fase_pertumbuhan=fase_display,
            rekomendasi_pupuk=rekomendasi,
            unsur_prioritas=unsur,
            pestisida_pendamping=pestisida_text,
            catatan_aplikasi=aplikasi
        )
