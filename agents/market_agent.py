from typing import Optional
from google import genai
from core.config import settings
from core.logger import logger
from agents.schemas import CommodityPriceResult, CommodityPriceItem
from agents.prompts import PRICE_SYSTEM_PROMPT


class MarketAgent:
    """Agent penyedia informasi transparansi harga pasar komoditas pangan harian."""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model_name = settings.gemini_model
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def get_reference_prices(self, query: str) -> CommodityPriceResult:
        """Mengembalikan data harga acuan komoditas pangan terkini dengan Pydantic Output."""
        # Baseline data acuan pasar nasional (PIHPS / Pasar Induk)
        # Di tahap produksi, ini bisa dihubungkan ke API / Scraping realtime
        reference_data = [
            CommodityPriceItem(
                nama_komoditas="Cabai Rawit Merah",
                harga_rata_rata=42000,
                satuan="kg",
                sumber_data="Panel Harga Pangan Nasional",
                tanggal_pembaruan="Hari Ini",
                rekomendasi_tengkulak="Sortir cabai matang sempurna dan petik tangkainya bersih untuk mendapatkan harga grade A."
            ),
            CommodityPriceItem(
                nama_komoditas="Cabai Merah Keriting",
                harga_rata_rata=35000,
                satuan="kg",
                sumber_data="Panel Harga Pangan Nasional",
                tanggal_pembaruan="Hari Ini",
                rekomendasi_tengkulak="Hindari memanen saat hujan lebat karena kadar air tinggi membuat buah cepat busuk dan harga ditekan."
            ),
            CommodityPriceItem(
                nama_komoditas="Gabah Kering Panen (GKP)",
                harga_rata_rata=6700,
                satuan="kg",
                sumber_data="Badan Pangan Nasional (Bapanas)",
                tanggal_pembaruan="Hari Ini",
                rekomendasi_tengkulak="Pastikan kadar air gabah mendekati standar acuan pemerintah (HPP) agar harga tebas tidak dipotong drastis."
            ),
            CommodityPriceItem(
                nama_komoditas="Beras Medium",
                harga_rata_rata=13500,
                satuan="kg",
                sumber_data="Pasar Induk Beras Cipinang",
                tanggal_pembaruan="Hari Ini",
                rekomendasi_tengkulak="Jual dalam kemasan bersih atau gabungkan kuota panen melalui kelompok tani (Poktan)."
            ),
        ]

        if not self.client:
            return CommodityPriceResult(
                items=reference_data,
                catatan_pasar="Data acuan rata-rata nasional. Harga di tingkat petani (farmgate) biasanya berselisih 10-15% tergantung jarak pengiriman ke pasar induk."
            )

        prompt = f"""\
{PRICE_SYSTEM_PROMPT}

Kueri Petani: "{query}"

Berdasarkan data acuan harga pasar komoditas pangan:
- Cabai Rawit Merah: Rp 40.000 - Rp 45.000 / kg
- Cabai Merah Keriting: Rp 32.000 - Rp 38.000 / kg
- Gabah Kering Panen (GKP): Rp 6.500 - Rp 7.000 / kg
- Beras Medium: Rp 13.000 - Rp 14.000 / kg

Format jawaban Anda ke dalam skema CommodityPriceResult dan berikan tips negosiasi praktis untuk petani agar tidak ditekan tengkulak.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": CommodityPriceResult,
                    "temperature": 0.2
                }
            )
            return response.parsed
        except Exception as e:
            logger.error(f"Gagal memproses analisis harga: {e}")
            return CommodityPriceResult(
                items=reference_data,
                catatan_pasar="Harga acuan dapat bervariasi sesuai kualitas fisik dan jarak tempuh ke pusat pasar grosir."
            )
