import unittest
from graph_builder import router_node, tani_graph_app, TaniState
from database.repository import ConsultationRepository
from agents.diagnosis_agent import DiagnosisAgent


class TestWeatherRoutingFlow(unittest.IsolatedAsyncioTestCase):
    """
    Memverifikasi perbaikan masalah input 'bantul' dan routing fitur cuaca
    agar tidak mental ke menu utama serta memastikan RAG database Supabase terambil.
    """

    async def test_bantul_routes_to_weather_not_greeting(self):
        """Input 'bantul' harus langsung dikenali sebagai intent weather, BUKAN greeting."""
        state: TaniState = {
            "phone_number": "628999999999",
            "user_message": "bantul",
            "media_id": None,
            "media_url": None,
            "intent": "diagnosis",
            "crop_context": None,
            "conversation_history": None,
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        routed = await router_node(state)
        self.assertEqual(routed.get("intent"), "weather")

        # Eksekusi graf lengkap dan pastikan hasilnya berisi informasi cuaca Bantul
        result = await tani_graph_app.ainvoke(state)
        self.assertEqual(result.get("intent"), "weather")
        final_text = result.get("final_response", "")
        self.assertIn("PRAKIRAAN CUACA PERTANIAN", final_text.upper())
        self.assertIn("BANTUL", final_text.upper())
        self.assertNotIn("SILAKAN PILIH MENU LAYANAN DI BAWAH INI", final_text.upper())

    async def test_quick_action_waktu_aman_semprot(self):
        """Pesan tombol '2. 🌦️ Waktu Aman Semprot' harus dikenali sebagai cuaca."""
        state: TaniState = {
            "phone_number": "628999999999",
            "user_message": "2. 🌦️ Waktu Aman Semprot",
            "media_id": None,
            "media_url": None,
            "intent": "diagnosis",
            "crop_context": None,
            "conversation_history": None,
            "is_first_interaction": False,
            "diagnosis_result": None,
            "price_result": None,
            "weather_result": None,
            "fertilizer_result": None,
            "history_result": None,
            "final_response": ""
        }
        routed = await router_node(state)
        self.assertIn(routed.get("intent"), ["weather", "weather_prompt"])

    async def test_knowledge_base_retrieval(self):
        """Memverifikasi bahwa pencarian knowledge_base di Supabase mengembalikan data resmi."""
        diag = DiagnosisAgent()
        vec = diag._get_embedding("daun cabai keriting rontok dan menguning")
        self.assertEqual(len(vec), 768)

        results = await ConsultationRepository.match_knowledge(
            query_embedding=vec,
            match_threshold=0.60,
            match_count=3,
            commodity="cabai"
        )
        self.assertGreater(len(results), 0)
        disease_names = [r.get("disease_name") for r in results]
        self.assertTrue(any("Thrips" in name or "Gemini" in name or "Layu" in name for name in disease_names))


if __name__ == "__main__":
    unittest.main()
