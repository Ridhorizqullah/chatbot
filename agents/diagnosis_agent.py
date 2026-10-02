import os
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from core.config import settings
from core.logger import logger
from agents.schemas import DiseaseDiagnosisResult, PracticalSteps
from agents.prompts import SYSTEM_PROMPT_DIAGNOSIS
from database.repository import ConsultationRepository


class DiagnosisAgent:
    """Agent diagnosa hama dan penyakit tanaman Cabai & Padi (Teks & Multimodal Vision)."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Gemini Client belum diinisialisasi karena GEMINI_API_KEY kosong.")

    def _get_embedding(self, text: str) -> List[float]:
        """Menghasilkan vector embedding untuk pencarian RAG di Supabase."""
        if not self.client:
            return []
        try:
            model = settings.embedding_model.replace("models/", "")
            config = {"output_dimensionality": 768} if "gemini-embedding" in model else None
            response = self.client.models.embed_content(
                model=model,
                contents=text,
                config=config,
            )
            return response.embeddings[0].values
        except Exception as e:
            logger.error(f"Gagal generate embedding: {e}")
            return []

    def _get_candidate_models(self) -> List[str]:
        # Dahulukan gemini-flash-latest untuk latensi tercepat dan minim antrean 503
        candidates = ["gemini-flash-latest"]
        if self.model_name and self.model_name.replace("models/", "") not in candidates:
            candidates.append(self.model_name.replace("models/", ""))
        for m in ["gemini-3.5-flash", "gemini-3.8-flash"]:
            if m not in candidates:
                candidates.append(m)
        return candidates

    def _generate_structured(self, contents: Any) -> Optional[DiseaseDiagnosisResult]:
        for model in self._get_candidate_models():
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": DiseaseDiagnosisResult,
                        "temperature": 0.2,
                    }
                )
                if response.parsed:
                    return response.parsed
            except Exception as e:
                logger.warning(f"Percobaan model '{model}' gagal: {e}. Mencoba model cadangan...")
        return None

    async def diagnose_text(self, user_query: str, crop_hint: Optional[str] = None) -> DiseaseDiagnosisResult:
        """Melakukan diagnosa berbasis teks dengan pencarian semantik RAG 11 Penyakit."""
        if not self.client:
            return DiseaseDiagnosisResult(
                is_supported_crop=True,
                nama_tanaman="cabai" if (crop_hint and "cabai" in crop_hint.lower()) else "padi",
                nama_penyakit="Belum Teridentifikasi (Mode Mock / API Key Belum Diset)",
                penyebab_biologis="Sistem",
                confidence_score=0.50,
                penjelasan_singkat="GEMINI_API_KEY belum dikonfigurasi di file .env.",
                langkah_penanganan=PracticalSteps(
                    mekanis="Periksa pengaturan sistem",
                    sanitasi="Pastikan konfigurasi lengkap",
                    bahan_aktif_kimiawi=None
                ),
                rujuk_ke_ppl=True,
                catatan_keamanan="Hubungi admin sistem."
            )

        # 1. RAG Retrieval via pgvector
        query_vec = self._get_embedding(user_query)
        context_docs = []
        if query_vec:
            context_docs = await ConsultationRepository.match_knowledge(
                query_embedding=query_vec,
                match_threshold=0.50,
                match_count=3,
                commodity=crop_hint
            )

        context_str = ""
        if context_docs:
            context_str = "\n\n".join([
                f"[Referensi Database 11 Penyakit: {doc.get('disease_name')} ({doc.get('scientific_name')})]\n"
                f"Komoditas: {doc.get('commodity')}\n"
                f"Penyebab: {doc.get('pathogen_type')}\n"
                f"Gejala Khas: {doc.get('symptoms')}\n"
                f"Mekanis: {doc.get('mechanical_treatment')}\n"
                f"Sanitasi: {doc.get('sanitation_treatment')}\n"
                f"Bahan Aktif: {doc.get('chemical_actives')}\n"
                f"Rekomendasi Pupuk: {doc.get('fertilizer_recommendation', '-')}"
                for doc in context_docs
            ])

        prompt = f"""\
{SYSTEM_PROMPT_DIAGNOSIS}

KONTEKS DATABASE RESMI (KNOWLEDGE BASE 11 PENYAKIT PADI & CABAI):
{context_str if context_str else "Tidak ada dokumen spesifik yang persis sama, lakukan analisis agronomi objektif."}

ATURAN VALIDASI TANAMAN:
- TaniPintar HANYA melayani tanaman CABAI (Capsicum annuum) dan PADI (Oryza sativa).
- Jika pengguna menanyakan tanaman lain (misal: sawit, jagung, apel, durian) atau bukan tanaman, set `is_supported_crop=False`, berikan `unsupported_message` bahwa bot khusus Cabai & Padi, dan set `confidence_score=0.0`.

PERTANYAAN / KELUHAN PETANI:
"{user_query}"

Kembalikan hasil diagnosis terstruktur sesuai skema DiseaseDiagnosisResult.
"""
        parsed_result = self._generate_structured(prompt)
        if parsed_result:
            return parsed_result
        return self._fallback_error_result("cabai" if (crop_hint and "cabai" in crop_hint.lower()) else "padi")

    async def diagnose_image(self, image_bytes: bytes, user_caption: str = "") -> DiseaseDiagnosisResult:
        """
        Melakukan diagnosa visual multimodal menggunakan Gemini Flash Vision.
        ATURAN MUTLAK: Hanya menerima foto CABAI dan PADI. Tanaman lain akan ditolak secara aman.
        """
        if not self.client:
            return self._fallback_error_result("cabai")

        prompt = f"""\
{SYSTEM_PROMPT_DIAGNOSIS}

TUGAS VISION MULTIMODAL:
Anda menerima foto kondisi fisik tanaman dari petani di lapangan.

ATURAN VALIDASI TANAMAN (SANGAT KETAT):
1. Periksa apakah foto ini benar-benar tanaman CABAI (Capsicum annuum) atau PADI (Oryza sativa).
2. JIKA BUKAN CABAI DAN BUKAN PADI (contoh: foto manusia, sawit, jagung, kopi, sayuran lain, atau benda mati):
   - Wajib set `is_supported_crop = False`
   - Wajib set `nama_tanaman = 'lainnya'`
   - Wajib set `confidence_score = 0.0`
   - Wajib isi `unsupported_message = 'Mohon maaf Bapak/Ibu Petani, layanan konsultasi foto TaniPintar saat ini KHUSUS didedikasikan untuk tanaman CABAI dan PADI. Foto yang dikirim terdeteksi bukan tanaman cabai atau padi. Silakan kirimkan foto daun, batang, atau buah cabai/padi Anda.'`
   - Selesai, jangan spekulasi nama penyakit.
3. JIKA BENAR CABAI ATAU PADI:
   - Cocokkan gejala visual dengan salah satu dari 11 Penyakit Utama:
     Cabai: (1) Antraknosa/Patek, (2) Virus Kuning Gemini/Bulai, (3) Layu Bakteri, (4) Layu Fusarium, (5) Thrips/Keriting Daun, (6) Bercak Daun Cercospora.
     Padi: (1) Blas Daun/Leher, (2) Hawar Daun Bakteri/Kresek, (3) Penggerek Batang (Sundep/Beluk), (4) Tungro, (5) Wereng Batang Coklat (WBC).
   - Tentukan confidence_score (0.0 - 1.0). Jika foto buram atau gejala tidak jelas, berikan confidence < 0.70 dan aktifkan rujuk_ke_ppl=True.
   - Sertakan langkah mekanis, sanitasi, dan bahan aktif anjuran.

Keterangan Tambahan Petani: "{user_caption}"
"""
        try:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            )
            parsed_result = self._generate_structured([prompt, image_part])
            if parsed_result:
                return parsed_result
        except Exception as e:
            logger.error(f"Error saat menyiapkan foto Gemini Vision: {e}")

        return self._fallback_error_result("cabai")

    def _fallback_error_result(self, crop_name: str) -> DiseaseDiagnosisResult:
        return DiseaseDiagnosisResult(
            is_supported_crop=True,
            nama_tanaman="cabai" if "cabai" in crop_name else "padi",
            nama_penyakit="Tidak Teridentifikasi",
            penyebab_biologis="Tidak Diketahui",
            confidence_score=0.40,
            penjelasan_singkat="Foto atau teks gejala tidak cukup jelas untuk dianalisis otomatis.",
            langkah_penanganan=PracticalSteps(
                mekanis="Hindari memotong bagian tanaman tanpa sterilisasi alat.",
                sanitasi="Jaga kebersihan drainase lahan.",
                bahan_aktif_kimiawi=None
            ),
            rujuk_ke_ppl=True,
            catatan_keamanan="Konsultasikan dengan Petugas Penyuluh Lapangan (PPL) setempat."
        )
