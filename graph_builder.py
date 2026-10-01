import re
from typing import TypedDict, Optional, Literal, Dict, Any, List
from langgraph.graph import StateGraph, END
from agents.schemas import (
    DiseaseDiagnosisResult,
    CommodityPriceResult,
    WeatherAdvisoryResult,
    FertilizerRecommendationResult
)
from agents.diagnosis_agent import DiagnosisAgent
from agents.fertilizer_agent import FertilizerAgent
from agents.prompts import SAFE_FALLBACK_MESSAGE
from services.whatsapp_service import WhatsAppService
from services.storage_service import StorageService
from services.price_service import PriceService
from services.weather_service import WeatherService
from database.repository import ConsultationRepository
from core.config import settings
from core.logger import logger


class TaniState(TypedDict):
    """Definisi State lengkap untuk 6 Fitur Utama TaniPintar di LangGraph."""
    phone_number: str
    user_message: str
    media_id: Optional[str]
    media_url: Optional[str]
    intent: Literal["diagnosis", "vision_diagnosis", "market_price", "history", "weather", "fertilizer", "greeting", "fallback"]
    crop_context: Optional[str]
    diagnosis_result: Optional[Dict[str, Any]]
    price_result: Optional[Dict[str, Any]]
    weather_result: Optional[Dict[str, Any]]
    fertilizer_result: Optional[Dict[str, Any]]
    history_result: Optional[List[Dict[str, Any]]]
    final_response: str


# Inisialisasi Singleton Agents & Services
diagnosis_agent = DiagnosisAgent()
fertilizer_agent = FertilizerAgent()
whatsapp_service = WhatsAppService()
storage_service = StorageService()
weather_service = WeatherService()


# ==========================================
# NODES (Fungsi Komponen LangGraph)
# ==========================================

async def router_node(state: TaniState) -> Dict[str, Any]:
    """Mendeteksi 6 intensi layanan TaniPintar berdasarkan teks atau media gambar."""
    msg = state.get("user_message", "").lower().strip()
    media_id = state.get("media_id")

    # 1. Fitur 2: Konsultasi Foto (Multimodal Vision)
    if media_id:
        return {"intent": "vision_diagnosis"}

    # Deteksi konteks tanaman (Cabai vs Padi)
    detected_crop = None
    if "cabai" in msg or "cabe" in msg:
        detected_crop = "cabai"
    elif "padi" in msg or "gabah" in msg or "sawah" in msg or "beras" in msg:
        detected_crop = "padi"

    # 2. Fitur 4: Riwayat Konsultasi
    history_keywords = ["riwayat", "histori", "rekam jejak", "konsultasi lalu", "konsultasi saya", "riwayat penyakit"]
    if any(k in msg for k in history_keywords):
        return {"intent": "history", "crop_context": detected_crop}

    # 3. Fitur 5: Prediksi Cuaca Pertanian
    weather_keywords = ["cuaca", "hujan", "mendung", "suhu", "angin", "prakiraan", "kapan nyemprot", "kelembapan", "gerimis"]
    if any(k in msg for k in weather_keywords):
        return {"intent": "weather", "crop_context": detected_crop}

    # 4. Fitur 3: Harga Pasar Padi dan Cabai (Otomatis & Admin)
    price_keywords = ["harga", "pasar", "sekilo", "per kilo", "jual", "tengkulak", "gkp", "gabah", "beras", "biaya"]
    if any(k in msg for k in price_keywords):
        return {"intent": "market_price", "crop_context": detected_crop}

    # 5. Fitur 6: Rekomendasi Pestisida & Pupuk Spesifik
    fertilizer_keywords = ["pupuk", "pemupukan", "dosis", "urea", "npk", "sp-36", "kcl", "kno3", "kalsium", "silika", "obat", "pestisida", "fungisida", "insektisida", "bakterisida", "semprot apa"]
    if any(k in msg for k in fertilizer_keywords):
        return {"intent": "fertilizer", "crop_context": detected_crop}

    # 6. Sapaan Umum & Bantuan
    greeting_keywords = ["halo", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "hai", "menu", "bantuan", "bisa apa", "fitur"]
    if any(msg == k or msg.startswith(f"{k} ") for k in greeting_keywords):
        return {"intent": "greeting", "crop_context": detected_crop}

    # 7. Fitur 1: Konsultasi Teks 11 Penyakit (Default)
    return {
        "intent": "diagnosis",
        "crop_context": detected_crop
    }


async def vision_node(state: TaniState) -> Dict[str, Any]:
    """
    Fitur 2: Menerima foto fisik, mengunduh dari Meta WA, mengunggah ke Supabase Storage,
    dan menganalisis gejala dengan Gemini Vision (KHUSUS CABAI DAN PADI).
    """
    media_id = state.get("media_id")
    phone = state.get("phone_number", "")
    caption = state.get("user_message", "").strip()

    if not media_id:
        return {"final_response": "Tidak ada media foto yang diterima."}

    logger.info(f"Mengunduh foto media ID {media_id} untuk nomor {phone}")
    image_bytes = await whatsapp_service.download_media(media_id)

    media_url = None
    if image_bytes:
        media_url = await storage_service.upload_crop_symptom_photo(phone, image_bytes)

    if not image_bytes:
        # Jika media gagal diunduh (misal mode dev tanpa token)
        return {
            "media_url": media_url,
            "final_response": "⚠️ Foto belum dapat diunduh dari WhatsApp. Silakan coba kirim ulang foto tanaman Anda."
        }

    # Analisis Multimodal Vision khusus Cabai & Padi
    result = await diagnosis_agent.diagnose_image(image_bytes, caption)
    return {
        "media_url": media_url,
        "diagnosis_result": result.model_dump(),
        "crop_context": result.nama_tanaman if result.is_supported_crop else None
    }


async def diagnosis_node(state: TaniState) -> Dict[str, Any]:
    """Fitur 1: Menjalankan RAG Semantik untuk 11 Penyakit Tanaman Cabai & Padi."""
    query = state.get("user_message", "")
    crop_context = state.get("crop_context")

    result = await diagnosis_agent.diagnose_text(query, crop_context)
    return {"diagnosis_result": result.model_dump()}


async def price_node(state: TaniState) -> Dict[str, Any]:
    """Fitur 3: Mengambil harga pasar komoditas (Update harian otomatis & input admin)."""
    query = state.get("user_message", "")
    result = await PriceService.get_daily_prices(query)
    return {"price_result": result.model_dump()}


async def history_node(state: TaniState) -> Dict[str, Any]:
    """Fitur 4: Mengambil riwayat konsultasi seorang petani dari tabel Supabase."""
    phone = state.get("phone_number", "")
    history_records = await ConsultationRepository.get_farmer_consultation_history(phone, limit=3)
    return {"history_result": history_records}


async def weather_node(state: TaniState) -> Dict[str, Any]:
    """Fitur 5: Mengambil data prakiraan cuaca Open-Meteo & advisory semprot."""
    query = state.get("user_message", "")
    # Ekstraksi nama daerah sederhana jika ada
    words = [w for w in query.replace("?", "").split() if len(w) > 3]
    loc_guess = words[-1] if words else "Karawang"
    if loc_guess.lower() in ["cuaca", "hujan", "hari", "besok", "lusa", "sawah"]:
        loc_guess = "Karawang"

    result = await weather_service.get_weather_forecast(loc_guess)
    return {"weather_result": result.model_dump()}


async def fertilizer_node(state: TaniState) -> Dict[str, Any]:
    """Fitur 6: Menghitung dosis dan formulasi pupuk serta pestisida spesifik."""
    query = state.get("user_message", "")
    crop_context = state.get("crop_context")
    result = fertilizer_agent.get_recommendation(query, crop_context)
    return {"fertilizer_result": result.model_dump()}


async def greeting_node(state: TaniState) -> Dict[str, Any]:
    """Menampilkan panduan 6 Layanan Lengkap MVP TaniPintar."""
    welcome_text = (
        "🌾 *Selamat Datang di TaniPintar Bot!*\n"
        "Asisten Sahabat Petani Cerdas untuk Perlindungan Tanaman Cabai & Padi.\n\n"
        "💡 *6 Layanan Utama yang Dapat Anda Gunakan:*\n"
        "1. 🔬 *Konsultasi Penyakit Teks:* Tanya gejala 11 penyakit cabai & padi.\n"
        "   _Contoh: 'Buah cabai saya ada bercak hitam melingkar membusuk'_\n"
        "2. 📸 *Konsultasi Foto:* Kirim foto daun/buah cabai & padi yang sakit.\n"
        "3. 📊 *Harga Pasar Harian:* Cek harga acuan cabai, gabah, dan beras se-Indonesia.\n"
        "   _Contoh: 'Berapa harga cabai rawit merah dan gabah hari ini?'_\n"
        "4. 📋 *Riwayat Konsultasi:* Ketik *'riwayat'* untuk melihat diagnosa sebelumnya.\n"
        "5. 🌦️ *Prediksi Cuaca & Semprot:* Cek kondisi cuaca & waktu aman semprot.\n"
        "   _Contoh: 'Bagaimana cuaca di Brebes hari ini, aman semprot?'_\n"
        "6. 🧪 *Rekomendasi Pupuk & Pestisida:* Takaran dosis nutrisi tanaman.\n"
        "   _Contoh: 'Rekomendasi pupuk cabai fase generatif berbuah lebat'_\n\n"
        "Silakan ketik pertanyaan Anda atau kirimkan foto tanaman!"
    )
    return {"final_response": welcome_text}


async def format_and_guardrail_node(state: TaniState) -> Dict[str, Any]:
    """Memformat output terstruktur ke WhatsApp Markdown dan menerapkan Guardrail Anti-Halusinasi."""
    if state.get("final_response"):
        return {}

    # 1. Output Fitur 4: Riwayat Konsultasi
    hist = state.get("history_result")
    if hist is not None:
        if not hist:
            msg = (
                "📋 *REKAM JEJAK KONSULTASI PETANI*\n\n"
                "Belum ditemukan riwayat konsultasi untuk nomor WhatsApp ini.\n"
                "Silakan konsultasikan gejala tanaman Cabai atau Padi Anda melalui teks atau foto!"
            )
            return {"final_response": msg}

        lines = ["📋 *REKAM JEJAK KONSULTASI ANDA:*\n"]
        for idx, item in enumerate(hist, 1):
            date_str = str(item.get("created_at", ""))[:10]
            crop = (item.get("crop_type") or "Tanaman").capitalize()
            disease = item.get("suspected_disease") or "Penyakit"
            conf = int(float(item.get("confidence_score", 0.0)) * 100)
            status_ppl = "⚠️ Rujuk PPL" if item.get("is_referred_to_ppl") else "✅ Teratasi Mandiri"

            lines.append(
                f"{idx}. *{crop} - {disease}* ({conf}%)\n"
                f"   📅 Tanggal: {date_str} | Status: {status_ppl}\n"
            )
        lines.append("ℹ️ _Ketik pertanyaan baru untuk melakukan konsultasi tanaman lanjutan._")
        return {"final_response": "\n".join(lines)}

    # 2. Output Fitur 5: Prediksi Cuaca
    weather = state.get("weather_result")
    if weather:
        msg = (
            f"🌦️ *PRAKIRAAN CUACA PERTANIAN ({weather.get('lokasi', '').upper()})*\n\n"
            f"• *Kondisi:* {weather.get('cuaca_saat_ini')}\n"
            f"• *Suhu Udara:* {weather.get('suhu_celsius')} °C\n"
            f"• *Kelembapan:* {weather.get('kelembapan_persen')}%\n"
            f"• *Peluang Hujan:* {weather.get('peluang_hujan_persen')}%\n\n"
            f"🚜 *Saran Aplikasi Penyemprotan:*\n{weather.get('advisory_penyemprotan')}\n\n"
            f"🌱 *Saran Pemupukan:*\n{weather.get('advisory_pemupukan')}"
        )
        return {"final_response": msg}

    # 3. Output Fitur 6: Rekomendasi Pupuk & Obat Spesifik
    fert = state.get("fertilizer_result")
    if fert:
        recs = "\n".join([f"• {r}" for r in fert.get("rekomendasi_pupuk", [])])
        pest = f"\n\n🛡️ *Pestisida Pendamping:*\n{fert.get('pestisida_pendamping')}" if fert.get("pestisida_pendamping") else ""
        msg = (
            f"🌱 *PANDUAN PEMUPUKAN & NUTRISI ({fert.get('nama_tanaman', '').upper()})*\n\n"
            f"📌 *Fase Tanaman:* {fert.get('fase_pertumbuhan')}\n"
            f"🎯 *Unsur Prioritas:* {fert.get('unsur_prioritas')}\n\n"
            f"📋 *Rekomendasi Dosis & Jenis Pupuk:*\n{recs}"
            f"{pest}\n\n"
            f"⚙️ *Petunjuk Waktu & Cara Aplikasi:*\n{fert.get('catatan_aplikasi')}"
        )
        return {"final_response": msg}

    # 4. Output Fitur 3: Harga Pasar
    price = state.get("price_result")
    if price:
        items_text = ""
        for item in price.get("items", []):
            prov = f"({item['provinsi']})" if item.get('provinsi') else ""
            items_text += (
                f"• *{item['komoditas']}* {prov}:\n"
                f"  - Harga Petani (Kebun): Rp {item['harga_petani']:,} /{item['satuan']}\n"
                f"  - Harga Pasar: Rp {item['harga_pasar']:,} /{item['satuan']}\n"
                f"  - _Tips Pasar:_ {item['tips_negosiasi']}\n\n"
            )
        msg = (
            "📊 *INFORMASI HARGA KOMODITAS PADI & CABAI*\n\n"
            f"{items_text}"
            f"ℹ️ *Sumber:* {price.get('sumber', '')}\n"
            f"📝 *Catatan:* {price.get('catatan_pasar', '')}"
        )
        return {"final_response": msg}

    # 5. Output Fitur 1 & 2: Diagnosis Teks atau Foto
    diag = state.get("diagnosis_result")
    if diag:
        # Pengecekan Khusus Cabai & Padi
        if not diag.get("is_supported_crop", True):
            return {"final_response": diag.get("unsupported_message") or "Mohon maaf, TaniPintar saat ini khusus melayani tanaman Cabai dan Padi."}

        confidence = diag.get("confidence_score", 0.0)
        rujuk_ppl = diag.get("rujuk_ke_ppl", False)

        # GUARDRAIL AMBANG BATAS KEYAKINAN (< 0.70)
        if confidence < settings.confidence_threshold or rujuk_ppl:
            logger.info(f"Guardrail aktif: Confidence {confidence} < {settings.confidence_threshold}")
            return {"final_response": SAFE_FALLBACK_MESSAGE}

        langkah = diag.get("langkah_penanganan", {})
        photo_info = "\n📸 _(Analisis Berdasarkan Bukti Foto Lapangan)_" if state.get("media_url") else ""
        msg = (
            f"🌿 *HASIL DIAGNOSIS TANAMAN ({diag.get('nama_tanaman', '').upper()})*{photo_info}\n\n"
            f"🎯 *Indikasi:* {diag.get('nama_penyakit')} "
            f"({diag.get('nama_ilmiah') or 'Patogen'})\n"
            f"🔬 *Penyebab:* {diag.get('penyebab_biologis')}\n"
            f"📊 *Tingkat Keyakinan:* {int(confidence * 100)}%\n\n"
            f"📝 *Penjelasan Gejala:*\n{diag.get('penjelasan_singkat')}\n\n"
            f"🛠️ *LANGKAH PENANGANAN PRAKTIS (3 PILAR):*\n"
            f"1. *Fisik / Mekanis:*\n   {langkah.get('mekanis')}\n\n"
            f"2. *Sanitasi Lahan & Drainase:*\n   {langkah.get('sanitasi')}\n\n"
            f"3. *Bahan Aktif Kimiawi (Jika Diperlukan):*\n   {langkah.get('bahan_aktif_kimiawi') or 'Tidak diperlukan bahan kimiawi.'}\n\n"
            f"⚠️ *Catatan Keselamatan:*\n{diag.get('catatan_keamanan')}\n\n"
            f"_Apabila gejala tidak membaik dalam 3-5 hari, segera hubungi PPL setempat._"
        )
        return {"final_response": msg}

    return {"final_response": SAFE_FALLBACK_MESSAGE}


async def audit_saver_node(state: TaniState) -> Dict[str, Any]:
    """Menyimpan rekam jejak konsultasi ke Supabase untuk audit PPL & memory session."""
    phone = state.get("phone_number", "")
    diag = state.get("diagnosis_result")

    if diag and diag.get("is_supported_crop", True):
        await ConsultationRepository.save_consultation_audit(
            phone_number=phone,
            crop_type=diag.get("nama_tanaman"),
            suspected_disease=diag.get("disease_name") or diag.get("nama_penyakit"),
            confidence_score=diag.get("confidence_score", 0.0),
            is_referred_to_ppl=diag.get("rujuk_ke_ppl", False) or diag.get("confidence_score", 0.0) < settings.confidence_threshold,
            media_url=state.get("media_url"),
            farmer_query=state.get("user_message", ""),
            bot_recommendation=diag
        )

    # Simpan status sesi percakapan
    await ConsultationRepository.upsert_session(
        phone_number=phone,
        current_state={"last_intent": state.get("intent")},
        last_crop_context=state.get("crop_context")
    )
    return {}


# ==========================================
# WORKFLOW GRAPH CONSTRUCTION
# ==========================================

def route_intent(state: TaniState) -> str:
    """Fungsi conditional routing LangGraph untuk 6 Layanan MVP."""
    intent = state.get("intent")
    if intent == "vision_diagnosis":
        return "vision"
    elif intent == "market_price":
        return "price"
    elif intent == "history":
        return "history"
    elif intent == "weather":
        return "weather"
    elif intent == "fertilizer":
        return "fertilizer"
    elif intent == "greeting":
        return "greeting"
    else:
        return "diagnosis"


def build_tani_graph():
    """Membangun StateGraph LangGraph lengkap untuk 6 Fitur MVP."""
    workflow = StateGraph(TaniState)

    # Daftarkan Seluruh Node Layanan
    workflow.add_node("router", router_node)
    workflow.add_node("vision", vision_node)
    workflow.add_node("diagnosis", diagnosis_node)
    workflow.add_node("price", price_node)
    workflow.add_node("history", history_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("fertilizer", fertilizer_node)
    workflow.add_node("greeting", greeting_node)
    workflow.add_node("formatter", format_and_guardrail_node)
    workflow.add_node("audit_saver", audit_saver_node)

    # Entrypoint
    workflow.set_entry_point("router")

    # Conditional Edges dari Router ke 6 Node Layanan
    workflow.add_conditional_edges(
        "router",
        route_intent,
        {
            "vision": "vision",
            "diagnosis": "diagnosis",
            "price": "price",
            "history": "history",
            "weather": "weather",
            "fertilizer": "fertilizer",
            "greeting": "greeting",
        }
    )

    # Seluruh node layanan terhubung ke formatter
    workflow.add_edge("vision", "formatter")
    workflow.add_edge("diagnosis", "formatter")
    workflow.add_edge("price", "formatter")
    workflow.add_edge("history", "formatter")
    workflow.add_edge("weather", "formatter")
    workflow.add_edge("fertilizer", "formatter")
    workflow.add_edge("greeting", "formatter")

    # Formatter lanjut ke audit saver lalu END
    workflow.add_edge("formatter", "audit_saver")
    workflow.add_edge("audit_saver", END)

    return workflow.compile()


# Instance singleton app graph
tani_graph_app = build_tani_graph()
