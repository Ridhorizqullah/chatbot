from typing import Optional
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

    def get_recommendation(self, query: str, crop_hint: Optional[str] = None) -> FertilizerRecommendationResult:
        """Menghasilkan rekomendasi pupuk dan pestisida terstruktur berdasarkan pertanyaan petani."""
        crop = "padi" if (crop_hint and "padi" in crop_hint.lower()) or ("padi" in query.lower() or "gabah" in query.lower() or "sawah" in query.lower()) else "cabai"
        is_generatif = any(w in query.lower() for w in ["bunga", "buah", "malai", "bunting", "panen", "rontok", "generatif"])
        fase = "Generatif (Pembungaan / Pembuahan / Pengisian Bulir)" if is_generatif else "Vegetatif (Pertumbuhan Daun & Tunas / Anakan)"

        # Standar agronomi resmi Kementerian Pertanian
        if crop == "cabai":
            if is_generatif:
                rekomendasi = [
                    "KNO3 Putih (Kalium Nitrat): 3-5 kg per 200 liter air (kocor 200 ml/tanaman tiap minggu) untuk bobot dan ketahanan kulit buah.",
                    "MKP (Mono Kalium Fosfat): 3-5 gram/liter semprot daun untuk memperkuat tangkai bunga agar tidak rontok.",
                    "Kalsium Boron (CaB): 2 gram/liter semprot seminggu sekali untuk mencegah busuk ujung buah (blossom end rot) dan patek."
                ]
                unsur = "Kalium (K), Fosfat (P), Kalsium (Ca), dan Boron (B)"
                pestisida = "Fungisida Mankozeb (kontak) selang-seling Difenokonazol (sistemik) bila cuaca sering gerimis."
                aplikasi = "Aplikasi kocor pada pagi hari setelah bedengan basah, dan semprot pupuk daun pukul 07.00 - 09.00."
            else:
                rekomendasi = [
                    "Pupuk NPK 16-16-16 (Mutiara/YaraMila): 2-3 kg per 200 liter air, kocor 150 ml per lubang tanam tiap 7-10 hari.",
                    "Asam Humat: 1-2 gram/liter kocor bersamaan NPK untuk memacu perakaran baru.",
                    "Pupuk Daun Tinggi Nitrogen & Magnesium (Mg): 2 gram/liter semprot interval 7 hari untuk warna daun hijau pekat."
                ]
                unsur = "Nitrogen (N) berimbang, Fosfat (P), dan Magnesium (Mg)"
                pestisida = "Insektisida Abamektin (0.5 ml/liter) jika ada gejala serangan thrips daun keriting."
                aplikasi = "Kocor merata di sekitar lingkar tajuk tanaman, hindari mengenai batang utama secara langsung."
        else:
            # Padi
            if is_generatif:
                rekomendasi = [
                    "Pemupukan Susulan II (Fase Bunting 35-45 HST): NPK Phonska 100 kg/ha + KCl (Kalium Klorida) 50 kg/ha.",
                    "Silika Cair (Si) + Pupuk Kalium Cair: Semprot daun saat bunting tua untuk memperkuat tangkai malai dan mencegah patah leher (blas leher).",
                    "Stop total aplikasi pupuk Urea (Nitrogen) murni saat padi mulai keluar malai."
                ]
                unsur = "Kalium (K) dan Silika (Si)"
                pestisida = "Fungisida bahan aktif Trisiklazol atau Difenokonazol saat padi bunting 5% dan bunting 70%."
                aplikasi = "Taburkan pupuk saat macak-macak (tanah lembap basah, jangan tergenang air dalam)."
            else:
                rekomendasi = [
                    "Pemupukan Dasar (0-7 HST): NPK Phonska 150 kg/ha + Urea 50 kg/ha.",
                    "Pemupukan Susulan I (21 HST): Urea 100 kg/ha + SP-36 / NPK 50 kg/ha untuk memicu anakan produktif maksimum."
                ]
                unsur = "Nitrogen (N) dan Fosfat (P)"
                pestisida = "Insektisida butiran Karbofuran 3GR (15-20 kg/ha) bila tampak ngengat penggerek batang sundep."
                aplikasi = "Tabur merata di petakan sawah saat air dangkal 2-3 cm, lalu biarkan 3 hari tanpa membuang air irigasi."

        if not self.client:
            return FertilizerRecommendationResult(
                nama_tanaman=crop,
                fase_pertumbuhan=fase,
                rekomendasi_pupuk=rekomendasi,
                unsur_prioritas=unsur,
                pestisida_pendamping=pestisida,
                catatan_aplikasi=aplikasi
            )

        prompt = f"""\
Anda adalah pakar nutrisi tanaman pangan dan hortikultura di Indonesia.
Petani bertanya seputar pupuk/pestisida: "{query}"
Target Tanaman: {crop.upper()}
Fase: {fase}

Panduan Resmi:
- Rekomendasi: {rekomendasi}
- Unsur: {unsur}
- Pestisida: {pestisida}
- Cara Aplikasi: {aplikasi}

Kembalikan jawaban terstruktur dalam skema FertilizerRecommendationResult dengan takaran tepat, aman, dan aplikatif.
"""
        candidate_models = ["gemini-flash-latest"]
        if self.model_name and self.model_name.replace("models/", "") not in candidate_models:
            candidate_models.append(self.model_name.replace("models/", ""))
        for m in ["gemini-3.5-flash", "gemini-3.8-flash"]:
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
            fase_pertumbuhan=fase,
            rekomendasi_pupuk=rekomendasi,
            unsur_prioritas=unsur,
            pestisida_pendamping=pestisida,
            catatan_aplikasi=aplikasi
        )
