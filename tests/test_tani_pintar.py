import unittest
import asyncio
import json
from pathlib import Path
from agents.schemas import (
    DiseaseDiagnosisResult,
    PracticalSteps,
    CommodityPriceResult,
    CommodityPriceItem,
    WeatherAdvisoryResult,
    FertilizerRecommendationResult
)
from graph_builder import route_intent, format_and_guardrail_node, router_node, TaniState
from agents.fertilizer_agent import FertilizerAgent
from services.price_service import PriceService
from core.config import settings


class TestTaniPintar6Features(unittest.TestCase):
    """Pengujian Unit & Validasi Komprehensif 6 Fitur MVP TaniPintar Bot."""

    def test_feature_1_knowledge_base_11_diseases(self):
        """Fitur 1: Memverifikasi tepat 11 penyakit dalam Knowledge Base (6 Cabai, 5 Padi)."""
        base_dir = Path(__file__).parent.parent / "data" / "knowledge"
        cabai_file = base_dir / "cabai_diseases.json"
        padi_file = base_dir / "padi_diseases.json"

        with open(cabai_file, "r", encoding="utf-8") as f:
            cabai_data = json.load(f)
        with open(padi_file, "r", encoding="utf-8") as f:
            padi_data = json.load(f)

        self.assertEqual(len(cabai_data), 6, "Cabai wajib memiliki tepat 6 penyakit.")
        self.assertEqual(len(padi_data), 5, "Padi wajib memiliki tepat 5 penyakit.")
        self.assertEqual(len(cabai_data) + len(padi_data), 11, "Total Knowledge Base wajib 11 penyakit.")

        # Cek setiap penyakit memiliki atribut wajib
        for item in cabai_data + padi_data:
            self.assertIn("disease_name", item)
            self.assertIn("scientific_name", item)
            self.assertIn("pathogen_type", item)
            self.assertIn("symptoms", item)
            self.assertIn("mechanical_treatment", item)
            self.assertIn("sanitation_treatment", item)
            self.assertIn("chemical_actives", item)
            self.assertIn("fertilizer_recommendation", item)

    def test_feature_2_crop_restriction_guardrail(self):
        """Fitur 2: Memverifikasi penolakan aman jika foto/kueri bukan tanaman Cabai atau Padi."""
        unsupported_diag = {
            "is_supported_crop": False,
            "unsupported_message": "Mohon maaf Bapak/Ibu Petani, TaniPintar saat ini khusus melayani tanaman CABAI dan PADI.",
            "nama_tanaman": "lainnya",
            "nama_penyakit": "-",
            "penyebab_biologis": "-",
            "confidence_score": 0.0,
            "penjelasan_singkat": "-",
            "langkah_penanganan": {"mekanis": "-", "sanitasi": "-", "bahan_aktif_kimiawi": None},
            "rujuk_ke_ppl": True,
            "catatan_keamanan": "-"
        }

        state: TaniState = {
            "phone_number": "628123456789",
            "user_message": "foto daun kelapa sawit",
            "media_id": "media_123",
            "media_url": "https://storage.supabase.co/foto_sawit.jpg",
            "intent": "vision_diagnosis",
            "crop_context": None,
            "diagnosis_result": unsupported_diag,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }

        res = asyncio.run(format_and_guardrail_node(state))
        self.assertIn("khusus melayani tanaman CABAI dan PADI", res["final_response"])

    def test_feature_3_daily_market_price_auto_update(self):
        """Fitur 3: Memverifikasi update harga pasar harian padi dan cabai se-Indonesia."""
        res: CommodityPriceResult = asyncio.run(PriceService.get_daily_prices("harga cabai rawit di Jawa Timur"))
        self.assertGreater(len(res.items), 0)
        item = res.items[0]
        self.assertGreater(item.harga_petani, 0)
        self.assertGreater(item.harga_pasar, item.harga_petani)
        self.assertIn("kg", item.satuan)

    def test_feature_4_consultation_history_formatting(self):
        """Fitur 4: Memverifikasi format kartu riwayat konsultasi petani."""
        mock_history = [
            {
                "created_at": "2026-10-01T10:00:00Z",
                "crop_type": "cabai",
                "suspected_disease": "Antraknosa / Patek",
                "confidence_score": 0.85,
                "is_referred_to_ppl": False
            },
            {
                "created_at": "2026-09-25T08:30:00Z",
                "crop_type": "padi",
                "suspected_disease": "Blas Daun",
                "confidence_score": 0.65,
                "is_referred_to_ppl": True
            }
        ]

        state: TaniState = {
            "phone_number": "628123456789",
            "user_message": "cek riwayat konsultasi saya",
            "media_id": None,
            "media_url": None,
            "intent": "history",
            "crop_context": None,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": mock_history,
            "final_response": ""
        }

        res = asyncio.run(format_and_guardrail_node(state))
        self.assertIn("REKAM JEJAK KONSULTASI ANDA", res["final_response"])
        self.assertIn("Antraknosa / Patek", res["final_response"])
        self.assertIn("Rujuk PPL", res["final_response"])

    def test_feature_5_weather_advisory_formatting(self):
        """Fitur 5: Memverifikasi format prediksi cuaca dan advisory semprot."""
        mock_weather = {
            "lokasi": "Brebes",
            "cuaca_saat_ini": "Cerah Berawan",
            "suhu_celsius": 29.5,
            "kelembapan_persen": 75,
            "peluang_hujan_persen": 15,
            "advisory_penyemprotan": "Kondisi kondusif untuk penyemprotan pagi hari.",
            "advisory_pemupukan": "Pemupukan aman dilakukan."
        }

        state: TaniState = {
            "phone_number": "628123456789",
            "user_message": "cuaca brebes",
            "media_id": None,
            "media_url": None,
            "intent": "weather",
            "crop_context": None,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": mock_weather,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }

        res = asyncio.run(format_and_guardrail_node(state))
        self.assertIn("PRAKIRAAN CUACA PERTANIAN (BREBES)", res["final_response"])
        self.assertIn("Saran Aplikasi Penyemprotan", res["final_response"])

    def test_feature_6_fertilizer_and_pesticide_recommendation(self):
        """Fitur 6: Memverifikasi rekomendasi spesifik pupuk & pestisida fase generatif cabai."""
        agent = FertilizerAgent()
        res: FertilizerRecommendationResult = agent.get_recommendation(
            query="rekomendasi pupuk cabai saat mulai berbuah dan berbunga",
            crop_hint="cabai"
        )

        self.assertEqual(res.nama_tanaman, "cabai")
        self.assertIn("Generatif", res.fase_pertumbuhan)
        self.assertGreater(len(res.rekomendasi_pupuk), 0)
        self.assertIn("KNO3", res.rekomendasi_pupuk[0])
        self.assertIsNotNone(res.pestisida_pendamping)

    def test_all_6_router_intents(self):
        """Memverifikasi router_node mengenali seluruh 6 intent MVP dengan tepat."""
        # 1. Foto
        s1: TaniState = {"user_message": "", "media_id": "img_123"}
        self.assertEqual(asyncio.run(router_node(s1))["intent"], "vision_diagnosis")

        # 2. Riwayat
        s2: TaniState = {"user_message": "riwayat saya", "media_id": None}
        self.assertEqual(asyncio.run(router_node(s2))["intent"], "history")

        # 3. Cuaca
        s3: TaniState = {"user_message": "bagaimana cuaca di sawah karawang?", "media_id": None}
        self.assertEqual(asyncio.run(router_node(s3))["intent"], "weather")

        # 4. Harga
        s4: TaniState = {"user_message": "berapa harga gabah gkp hari ini?", "media_id": None}
        self.assertEqual(asyncio.run(router_node(s4))["intent"], "market_price")

        # 5. Pupuk
        s5: TaniState = {"user_message": "dosis pupuk urea dan npk padi", "media_id": None}
        self.assertEqual(asyncio.run(router_node(s5))["intent"], "fertilizer")

        # 6. Diagnosis Teks
        s6: TaniState = {"user_message": "daun cabai keriting menguning bercak", "media_id": None}
        self.assertEqual(asyncio.run(router_node(s6))["intent"], "diagnosis")


if __name__ == "__main__":
    unittest.main()
