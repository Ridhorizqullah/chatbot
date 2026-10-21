import unittest
import asyncio
from graph_builder import tani_graph_app


class TestPriceInteractiveFlow(unittest.TestCase):
    def test_price_conversational_step_by_step(self):
        async def run_steps():
            # Step 1: Petani klik Cek Harga Pasar dari WhatsApp List
            s1 = {
                "phone_number": "6289999999999",
                "user_message": "Cek Harga Pasar\nHarga cabai & padi hari ini",
                "media_id": None, "media_url": None, "intent": "diagnosis",
                "crop_context": "cabai", "conversation_history": None,
                "is_first_interaction": False, "session_state": {"step": "main_menu"},
                "diagnosis_result": None, "price_result": None, "weather_result": None,
                "fertilizer_result": None, "history_result": None, "final_response": ""
            }
            r1 = await tani_graph_app.ainvoke(s1)
            self.assertEqual(r1.get("intent"), "price_prompt")
            self.assertEqual((r1.get("session_state") or {}).get("step"), "awaiting_price_commodity")
            self.assertIn("Padi & Beras", r1.get("final_response"))

            # Step 2: Petani memilih komoditas Cabai
            s2 = {
                "phone_number": "6289999999999",
                "user_message": "btn_harga_cabai",
                "media_id": None, "media_url": None, "intent": "diagnosis",
                "crop_context": None, "conversation_history": None,
                "is_first_interaction": False, "session_state": r1.get("session_state"),
                "diagnosis_result": None, "price_result": None, "weather_result": None,
                "fertilizer_result": None, "history_result": None, "final_response": ""
            }
            r2 = await tani_graph_app.ainvoke(s2)
            self.assertEqual(r2.get("intent"), "price_region_prompt")
            self.assertEqual((r2.get("session_state") or {}).get("step"), "awaiting_price_region")
            self.assertIn("Bantul", r2.get("final_response"))

            # Step 3: Petani memilih wilayah Bantul
            s3 = {
                "phone_number": "6289999999999",
                "user_message": "bantul",
                "media_id": None, "media_url": None, "intent": "diagnosis",
                "crop_context": "Cabai", "conversation_history": None,
                "is_first_interaction": False, "session_state": r2.get("session_state"),
                "diagnosis_result": None, "price_result": None, "weather_result": None,
                "fertilizer_result": None, "history_result": None, "final_response": ""
            }
            r3 = await tani_graph_app.ainvoke(s3)
            self.assertEqual(r3.get("intent"), "market_price")
            self.assertIn("Cabai", r3.get("final_response"))
            self.assertIn("Bantul", r3.get("final_response"))
            # Pastikan tidak ada Beras yang tercampur saat user memilih Cabai
            self.assertNotIn("Beras Kualitas", r3.get("final_response"))

            # Step 4: Direct query "harga beras di sleman"
            s4 = {
                "phone_number": "6289999999999",
                "user_message": "harga beras di sleman",
                "media_id": None, "media_url": None, "intent": "diagnosis",
                "crop_context": None, "conversation_history": None,
                "is_first_interaction": False, "session_state": {"step": "main_menu"},
                "diagnosis_result": None, "price_result": None, "weather_result": None,
                "fertilizer_result": None, "history_result": None, "final_response": ""
            }
            r4 = await tani_graph_app.ainvoke(s4)
            self.assertEqual(r4.get("intent"), "market_price")
            self.assertIn("Beras", r4.get("final_response"))
            self.assertNotIn("Cabai Rawit", r4.get("final_response"))

            # Step 5: Input "bantul" di menu utama harus ke cuaca (bukan harga)
            s5 = {
                "phone_number": "6289999999999",
                "user_message": "bantul",
                "media_id": None, "media_url": None, "intent": "diagnosis",
                "crop_context": None, "conversation_history": None,
                "is_first_interaction": False, "session_state": {"step": "main_menu"},
                "diagnosis_result": None, "price_result": None, "weather_result": None,
                "fertilizer_result": None, "history_result": None, "final_response": ""
            }
            r5 = await tani_graph_app.ainvoke(s5)
            self.assertEqual(r5.get("intent"), "weather")

        asyncio.run(run_steps())


if __name__ == "__main__":
    unittest.main()
