import os
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from core.config import settings
from core.logger import logger
from agents.schemas import DiseaseDiagnosisResult, PracticalSteps
from agents.prompts import SYSTEM_PROMPT_DIAGNOSIS
from database.repository import ConsultationRepository
from services.cv_preprocessor import CVPreprocessor, CVQualityResult
from services.visual_rag_service import VisualRAGService, VisualMatchResult


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
        
        # Inisialisasi Visual RAG Image Vector Search
        self.visual_rag = VisualRAGService()

    def _get_embedding(self, text: str) -> List[float]:
        """Menghasilkan vector embedding untuk pencarian RAG di Supabase."""
        if not self.client:
            return []
        try:
            # Gunakan gemini-embedding-001 (768 dimensi) yang konsisten dengan vektor di database knowledge_base
            model = "gemini-embedding-001"
            config = {"output_dimensionality": 768}
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
        # Dahulukan gemini-3.5-flash-lite untuk kehandalan, latensi tercepat, dan bebas antrean 503
        candidates = ["gemini-3.5-flash-lite", "gemini-flash-lite-latest", "gemini-3.1-flash-lite"]
        if self.model_name and self.model_name.replace("models/", "") not in candidates:
            candidates.append(self.model_name.replace("models/", ""))
        for m in ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3.8-flash"]:
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

    async def diagnose_text(
        self,
        user_query: str,
        crop_hint: Optional[str] = None,
        conversation_history: Optional[str] = None
    ) -> DiseaseDiagnosisResult:
        """Melakukan diagnosa berbasis teks dengan pencarian semantik RAG 11 Penyakit dan memori percakapan multi-turn."""
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
        rag_search_text = f"{user_query} {crop_hint or ''}".strip()
        query_vec = self._get_embedding(rag_search_text)
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

        history_section = ""
        if conversation_history:
            history_section = (
                f"\n\nRIWAYAT PERCAKAPAN & DIAGNOSIS SEBELUMNYA (MULTI-TURN CONTEXT MEMORY):\n"
                f"{conversation_history}\n\n"
                f"PETUNJUK MEMORI PERCAKAPAN:\n"
                f"- Petani mungkin menanyakan kelanjutan atau detail dari konsultasi sebelumnya (misalnya: 'obatnya apa?', 'dosisnya berapa?', 'bagaimana cara semprotnya?').\n"
                f"- Hubungkan jawaban dan rekomendasi secara koheren dengan tanaman ({crop_hint or 'Cabai/Padi'}) dan penyakit yang dibahas sebelumnya.\n"
                f"- JANGAN menolak pertanyaan lanjutan petani sebagai tanaman tidak didukung bila percakapan sebelumnya membahas Cabai atau Padi."
            )

        prompt = f"""\
{SYSTEM_PROMPT_DIAGNOSIS}

KONTEKS DATABASE RESMI (KNOWLEDGE BASE 11 PENYAKIT PADI & CABAI):
{context_str if context_str else "Tidak ada dokumen spesifik yang persis sama, lakukan analisis agronomi objektif."}
{history_section}

ATURAN VALIDASI TANAMAN:
- TaniPintar HANYA melayani tanaman CABAI (Capsicum annuum) dan PADI (Oryza sativa).
- Jika pengguna menanyakan tanaman lain (misal: sawit, jagung, apel, durian) atau bukan tanaman sama sekali, set `is_supported_crop=False`, berikan `unsupported_message` bahwa bot khusus Cabai & Padi, dan set `confidence_score=0.0`.
- Jika pertanyaan merupakan pertanyaan lanjutan dari konsultasi cabai/padi sebelumnya, tetap layani dengan `is_supported_crop=True`.

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
        Alur Diagnosa Visual Komprehensif:
        1. OpenCV Preprocessor (Blur & Plant Foliage Verification Gatekeeper).
        2. Visual RAG (Image-to-Image Vector Cosine Search di Supabase Gallery).
        3. Retrieval SOP Kementan Terkait (Text Knowledge RAG).
        4. Multimodal Synthesis (Gemini Flash Vision + Visual Reference + SOP Kementan).
        """
        if not self.client:
            return self._fallback_error_result("cabai")

        # ==========================================================
        # TAHAP 1: OpenCV Preprocessor (Quality & Plant Gatekeeper)
        # ==========================================================
        cv_res: CVQualityResult = CVPreprocessor.inspect_image(image_bytes)
        if not cv_res.is_valid:
            logger.warning(f"[DiagnosisAgent] Foto ditolak oleh OpenCV Preprocessor: {cv_res.rejection_reason}")
            return DiseaseDiagnosisResult(
                is_supported_crop=cv_res.is_plant,
                unsupported_message=cv_res.rejection_reason,
                nama_tanaman="cabai",
                nama_penyakit="Kualitas Citra Tidak Memenuhi Standar",
                penyebab_biologis="Prapemrosesan Citra (OpenCV)",
                confidence_score=0.0,
                penjelasan_singkat=cv_res.rejection_reason or "Kualitas citra belum memadai untuk diagnosa.",
                langkah_penanganan=PracticalSteps(
                    mekanis="Ambil foto ulang lebih dekat dengan fokus stabil.",
                    sanitasi="Pastikan pencahayaan cukup terang dan objek daun/buah tampak jelas.",
                    bahan_aktif_kimiawi=None
                ),
                rujuk_ke_ppl=False,
                catatan_keamanan="Foto belum memenuhi standar ketajaman citra untuk dianalisis.",
                cv_blur_score=cv_res.blur_score,
                cv_plant_coverage=cv_res.plant_coverage,
                cv_organ_detected=cv_res.organ_hint
            )

        # ==========================================================
        # TAHAP 2: Visual RAG (Image-to-Image Vector Similarity Search)
        # ==========================================================
        visual_match: VisualMatchResult = self.visual_rag.search_similar_images(
            image_bytes=image_bytes,
            top_k=3,
            organ_filter=cv_res.organ_hint
        )

        visual_candidates_text = "\n".join([
            f"  - {m['disease_name']} ({m['organ']}): Kemiripan Visual {m['similarity_pct']}% (URL: {m['storage_url']})"
            for m in visual_match.top_matches
        ])

        # ==========================================================
        # TAHAP 3: Retrieval SOP Kementan Terkait (Text Knowledge RAG)
        # ==========================================================
        kb_context_str = ""
        if visual_match.has_match:
            try:
                query_vec = self._get_embedding(f"Penyakit {visual_match.best_disease_name} pada {cv_res.organ_hint}")
                if query_vec:
                    docs = await ConsultationRepository.match_knowledge(
                        query_embedding=query_vec,
                        match_threshold=0.50,
                        match_count=2,
                        commodity="cabai"
                    )
                    if docs:
                        kb_context_str = "\n".join([
                            f"[SOP Resmi Kementan: {d.get('disease_name')} ({d.get('scientific_name')})]\n"
                            f"Gejala: {d.get('symptoms')}\n"
                            f"Mekanis: {d.get('mechanical_treatment')}\n"
                            f"Sanitasi: {d.get('sanitation_treatment')}\n"
                            f"Bahan Aktif: {d.get('chemical_actives')}"
                            for d in docs
                        ])
            except Exception as e:
                logger.warning(f"Gagal mengambil teks RAG untuk visual match: {e}")

        # ==========================================================
        # TAHAP 4: Gemini Flash Vision Multimodal Synthesis
        # ==========================================================
        prompt = f"""\
{SYSTEM_PROMPT_DIAGNOSIS}

TUGAS VISION MULTIMODAL DENGAN BANTUAN OPENCV & VISUAL RAG:
Anda menerima foto kondisi fisik tanaman dari petani di lapangan.

HASIL ANALISIS OPENCV PREPROCESSOR:
- Skor Fokus/Ketajaman (Laplacian Var): {cv_res.blur_score:.1f} (Threshold: > {CVPreprocessor.BLUR_THRESHOLD})
- Estimasi Luas Area Tanaman: {cv_res.plant_coverage*100:.1f}%
- Estimasi Organ Tanaman: {cv_res.organ_hint}

HASIL VISUAL RAG (IMAGE-TO-IMAGE VECTOR SEARCH DI SUPABASE STORAGE):
- Indikasi Terkuat: {visual_match.best_disease_name} ({visual_match.scientific_name})
- Skor Kemiripan Visual Vektor: {visual_match.similarity_percentage}%
- Foto Referensi Supabase: {visual_match.reference_storage_url}
- 3 Kandidat Referensi Teratas:
{visual_candidates_text}

REFERENSI SOP KEMENTAN TERKAIT:
{kb_context_str if kb_context_str else "Gunakan basis pengetahuan standar 11 penyakit padi dan cabai."}

PETUNJUK ANALISIS:
1. Validasi apakah lesi pada foto petani cocok dengan kandidat Visual RAG di atas ({visual_match.best_disease_name}).
2. Jika sangat sesuai, gunakan nama penyakit dan patogen tersebut, serta integrasikan rekomendasi SOP Kementan (mekanis, sanitasi, bahan aktif).
3. Berikan confidence_score realistis (0.70 - 0.98) jika visual jelas.
4. Pastikan response sesuai skema JSON DiseaseDiagnosisResult.

Keterangan Tambahan Petani: "{user_caption}"
"""
        try:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg",
            )
            parsed_result = self._generate_structured([prompt, image_part])
            if parsed_result:
                parsed_result.visual_match_similarity = visual_match.similarity_percentage
                parsed_result.visual_reference_url = visual_match.reference_storage_url
                parsed_result.visual_match_reasoning = visual_match.visual_reasoning
                parsed_result.cv_blur_score = cv_res.blur_score
                parsed_result.cv_plant_coverage = cv_res.plant_coverage
                parsed_result.cv_organ_detected = cv_res.organ_hint
                return parsed_result
        except Exception as e:
            logger.error(f"Error saat menyiapkan foto Gemini Vision: {e}")

        fallback = self._fallback_error_result("cabai")
        fallback.visual_match_similarity = visual_match.similarity_percentage
        fallback.visual_reference_url = visual_match.reference_storage_url
        fallback.cv_blur_score = cv_res.blur_score
        fallback.cv_plant_coverage = cv_res.plant_coverage
        fallback.cv_organ_detected = cv_res.organ_hint
        return fallback

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
