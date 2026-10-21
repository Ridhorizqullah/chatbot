import re
from datetime import datetime, timezone
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

# ==========================================
# STATE TYPEDICT
# ==========================================

class TaniState(TypedDict):
    """Definisi State lengkap untuk 6 Fitur Utama TaniPintar di LangGraph."""
    phone_number: str
    user_message: str
    media_id: Optional[str]
    media_url: Optional[str]
    intent: Literal[
        "diagnosis", "vision_diagnosis", "market_price", "history",
        "weather", "fertilizer", "greeting", "fallback",
        "photo_instruction", "disease_text_prompt", "price_prompt",
        "price_region_prompt", "weather_prompt", "fertilizer_prompt"
    ]
    crop_context: Optional[str]
    conversation_history: Optional[str]
    awaiting_location: Optional[bool]
    session_state: Optional[Dict[str, Any]]
    diagnosis_result: Optional[Dict[str, Any]]
    price_result: Optional[Dict[str, Any]]
    weather_result: Optional[Dict[str, Any]]
    fertilizer_result: Optional[Dict[str, Any]]
    history_result: Optional[List[Dict[str, Any]]]
    is_first_interaction: Optional[bool]
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
    """
    Intent Classifier Langsung & Stateless untuk 6 Layanan TaniPintar.
    Mengembalikan arsitektur Dual-RAG direct sesuai Slide Deck Capstone:
      1. Jika ada gambar / media_id -> Langsung ke vision_diagnosis (Prioritas Utama).
      2. Jika berupa sapaan/kata "menu" -> Langsung ke greeting (pesan tunggal ringkas).
      3. Jika teks menyebut nama desa/kecamatan atau cuaca -> Langsung ke weather (BMKG Adm4).
      4. Jika teks menanyakan harga pasar/komoditas -> Langsung ke market_price.
      5. Jika teks menyebut pupuk/fase tanaman -> Langsung ke fertilizer.
      6. Jika teks mengandung keluhan hama/penyakit -> Langsung ke diagnosis (Semantic SOP RAG).
    """
    phone = state.get("phone_number", "")
    msg = state.get("user_message", "").lower().strip()
    media_id = state.get("media_id")

    # Bersihkan karakter tanda baca untuk pencocokan kata yang fleksibel
    clean_msg = re.sub(r"[^\w\s]", "", msg).strip()

    # 1. Cek sesi di database untuk menentukan greeting pembuka
    is_first_time = False
    if phone:
        try:
            session = await ConsultationRepository.get_session(phone)
            if not session:
                is_first_time = True
        except Exception as e:
            logger.debug(f"Gagal cek status sesi pertama kali: {e}")
            is_first_time = False

    # Deteksi konteks tanaman (Cabai vs Padi), pertahankan konteks dari sesi bila ada
    detected_crop = state.get("crop_context")
    if "cabai" in msg or "cabe" in msg:
        detected_crop = "cabai"
    elif "padi" in msg or "gabah" in msg or "sawah" in msg or "beras" in msg:
        detected_crop = "padi"

    # ==============================================================
    # 1. PRIORITAS UTAMA: Multimodal Vision saat media foto diterima
    # ==============================================================
    if media_id:
        return {
            "intent": "vision_diagnosis",
            "crop_context": detected_crop,
            "is_first_interaction": is_first_time
        }

    # ==============================================================
    # 2. Manajemen State Percakapan Terpandu (Multi-turn State Machine)
    # ==============================================================
    session_curr = state.get("session_state") or {}
    session_step = session_curr.get("step")
    stored_commodity = session_curr.get("commodity")

    # Kamus wilayah sentra pasar dan singkatan lokal (DIY & Magelang)
    known_regions = {
        "sleman": "Sleman",
        "bantul": "Bantul",
        "kulon progo": "Kulon Progo",
        "kulonprogo": "Kulon Progo",
        "wates": "Kulon Progo",
        "garongan": "Kulon Progo",
        "bugel": "Kulon Progo",
        "jogja": "Yogyakarta",
        "yogyakarta": "Yogyakarta",
        "magelang": "Magelang",
        "muntilan": "Magelang",
        "sawangan": "Magelang",
    }

    # Ekstraksi nama wilayah pasar dari pesan masuk
    detected_region = None
    if clean_msg.startswith("btn_region_"):
        r_key = clean_msg.replace("btn_region_", "").strip()
        detected_region = known_regions.get(r_key) or r_key.title()
    elif session_step == "awaiting_price_region" and clean_msg in ["1", "1."]:
        detected_region = "Sleman"
    elif session_step == "awaiting_price_region" and clean_msg in ["2", "2."]:
        detected_region = "Bantul"
    elif session_step == "awaiting_price_region" and clean_msg in ["3", "3."]:
        detected_region = "Kulon Progo"
    elif session_step == "awaiting_price_region" and clean_msg in ["4", "4."]:
        detected_region = "Yogyakarta"
    elif session_step == "awaiting_price_region" and clean_msg in ["5", "5."]:
        detected_region = "Magelang"
    else:
        for k_reg, v_reg in known_regions.items():
            if k_reg in clean_msg:
                detected_region = v_reg
                break

    # Ekstraksi nama komoditas pasar dari pesan masuk
    detected_price_commodity = None
    if any(k in clean_msg for k in ["cabai", "cabe", "rawit", "keriting", "btn_harga_cabai"]):
        detected_price_commodity = "Cabai"
    elif any(k in clean_msg for k in ["padi", "beras", "gabah", "gkp", "btn_harga_padi"]):
        detected_price_commodity = "Padi & Beras"
    elif session_step == "awaiting_price_commodity" and clean_msg in ["1", "1."]:
        detected_price_commodity = "Cabai"
    elif session_step == "awaiting_price_commodity" and clean_msg in ["2", "2."]:
        detected_price_commodity = "Padi & Beras"

    # Penanganan percakapan lanjutan: Pengguna sedang memilih Komoditas Pasar
    if session_step == "awaiting_price_commodity":
        if detected_price_commodity:
            if detected_region:
                return {
                    "intent": "market_price",
                    "user_message": f"{detected_price_commodity} di {detected_region}",
                    "crop_context": detected_price_commodity,
                    "session_state": {"step": "main_menu"}
                }
            return {
                "intent": "price_region_prompt",
                "crop_context": detected_price_commodity,
                "session_state": {"step": "awaiting_price_region", "commodity": detected_price_commodity}
            }

    # Penanganan percakapan lanjutan: Pengguna sedang memilih Wilayah Pasar
    if session_step == "awaiting_price_region":
        if detected_region:
            resolved_comm = stored_commodity or detected_crop or "Cabai"
            return {
                "intent": "market_price",
                "user_message": f"{resolved_comm} di {detected_region}",
                "crop_context": resolved_comm,
                "session_state": {"step": "main_menu"}
            }

    # ==============================================================
    # 3. Kata Kunci & Menu Harga Pasar Komoditas (Cabai & Padi)
    # ==============================================================
    price_prompt_phrases = [
        "cek harga", "cek harga pasar", "harga pasar", "info harga", "harga",
        "btn_cek_harga", "menu_harga", "3", "3.",
        "cek harga pasar harga cabai padi hari ini",
        "cek harga pasar harga cabai & padi hari ini",
        "harga cabai & padi hari ini",
        "harga cabai padi hari ini",
        "harga cabai dan padi hari ini"
    ]
    is_price_menu_clicked = (
        clean_msg in price_prompt_phrases or
        clean_msg in ["3", "3.", "btn_cek_harga", "menu_harga"] or
        clean_msg.startswith("cek harga") or
        clean_msg.startswith("harga pasar") or
        "btn_cek_harga" in clean_msg
    )

    price_keywords = [
        "harga", "pasar", "sekilo", "per kilo", "perkilo", "jual", "tengkulak",
        "gkp", "gabah", "beras", "biaya", "patokan", "btn_harga"
    ]
    has_price_kw = any(k in clean_msg for k in price_keywords) or "btn_harga" in clean_msg

    if is_price_menu_clicked:
        return {
            "intent": "price_prompt",
            "crop_context": detected_crop,
            "session_state": {"step": "awaiting_price_commodity"}
        }

    if has_price_kw:
        if detected_price_commodity and detected_region:
            return {
                "intent": "market_price",
                "user_message": f"{detected_price_commodity} di {detected_region}",
                "crop_context": detected_price_commodity,
                "session_state": {"step": "main_menu"}
            }
        elif detected_price_commodity:
            return {
                "intent": "price_region_prompt",
                "crop_context": detected_price_commodity,
                "session_state": {"step": "awaiting_price_region", "commodity": detected_price_commodity}
            }
        else:
            return {
                "intent": "price_prompt",
                "crop_context": detected_crop,
                "session_state": {"step": "awaiting_price_commodity"}
            }

    # ==============================================================
    # 4. Kata Kunci Lokasi & Cuaca Pertanian (BMKG Adm4)
    # ==============================================================
    weather_keywords = [
        "cuaca", "hujan", "mendung", "suhu", "angin", "prakiraan", "kapan nyemprot",
        "kelembapan", "gerimis", "panas", "adem", "nyemprot", "deras", "kilat", "petir",
        "waktu aman semprot", "aman semprot", "waktu semprot"
    ]
    admin_location_keywords = [
        "desa", "kelurahan", "kecamatan", "kabupaten", "kota", "dusun", "dukuh", "kampung"
    ]
    known_locations = [
        "sleman", "bantul", "kulon progo", "kulonprogo", "gunungkidul", "jogja", "yogyakarta",
        "magelang", "muntilan", "sawangan", "mertoyudan", "borobudur", "srumbung",
        "ngablak", "tempel", "turi", "pakem", "ngaglik", "kalasan", "prambanan",
        "sedayu", "pandak", "kretek", "kasihan", "sewon", "sentolo", "pengasih",
        "tuksono", "wates", "garongan", "panjatan", "imogiri", "wonosari", "pakis", "secang"
    ]

    has_weather_kw = any(k in msg for k in weather_keywords)
    has_admin_kw = any(k in clean_msg.split() for k in admin_location_keywords)
    has_known_loc = any(loc in msg for loc in known_locations)

    weather_prompt_phrases = [
        "info cuaca", "cek cuaca", "cuaca", "cuaca hari ini", "prakiraan cuaca",
        "btn_info_cuaca", "menu_cuaca", "4", "4.",
        "waktu aman semprot", "2 waktu aman semprot", "2. waktu aman semprot"
    ]

    if (clean_msg in weather_prompt_phrases or clean_msg in ["4", "4.", "btn_info_cuaca", "menu_cuaca"]) and not has_known_loc:
        return {"intent": "weather_prompt", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    if (has_known_loc or has_weather_kw or has_admin_kw) and not has_price_kw:
        return {"intent": "weather", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    # ==============================================================
    # 5. Rekomendasi Pupuk & Dosis Tanaman
    # ==============================================================
    fertilizer_keywords = [
        "pupuk", "pemupukan", "dosis", "urea", "npk", "sp-36", "sp36", "kcl", "kno3",
        "kalsium", "silika", "obat", "pestisida", "fungisida", "insektisida", "bakterisida",
        "semprot apa", "hst", "fase vegetatif", "fase generatif", "bunting",
        "dosis pupuk & obat", "dosis pupuk dan obat", "dosis pupuk obat"
    ]
    has_fert_kw = any(k in clean_msg for k in fertilizer_keywords)

    fertilizer_prompt_phrases = [
        "5", "5.", "btn_pupuk", "menu_pupuk", "panduan pupuk", "panduan pupuk & obat",
        "panduan pupuk dan obat", "panduan pupuk obat"
    ]
    if clean_msg in fertilizer_prompt_phrases:
        return {"intent": "fertilizer_prompt", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    if has_fert_kw:
        return {"intent": "fertilizer", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    # ==============================================================
    # 6. Sapaan Umum, Bantuan & Perintah Menu
    # ==============================================================
    greeting_triggers = [
        "halo", "hallo", "hello", "hai", "hi", "hey", "hei",
        "assalamualaikum", "assalamu'alaikum", "samlikum", "askum", "mikum",
        "p", "ping", "tes", "test",
        "pagi", "siang", "sore", "malam",
        "selamat pagi", "selamat siang", "selamat sore", "selamat malam",
        "permisi", "punten", "kulonuwun",
        "bisa bantu", "bisa tanya", "mau tanya",
        "bantuan", "help", "menu", "fitur",
        "mulai", "start", "awal", "batal", "reset", "bot", "tanipintar",
        "btn_menu", "btn_menu_utama"
    ]

    is_greeting_match = (
        clean_msg in greeting_triggers or
        any(clean_msg == k or clean_msg.startswith(f"{k} ") for k in greeting_triggers) or
        any(k in clean_msg for k in ["bisa bantu", "mau tanya", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"])
    )

    # Indikasi kata gejala spesifik penyakit tanaman (bukan kata umum menu)
    specific_symptoms = [
        "bercak", "busuk", "kuning", "keriting", "layu", "rontok",
        "ulat", "wereng", "kutu", "jamur", "bakteri",
        "kering", "bolong", "gosong", "bintik", "patek", "kresek"
    ]
    has_specific_symptom = any(s in clean_msg for s in specific_symptoms)
    has_symptom_word = has_specific_symptom or any(s in clean_msg for s in ["hama", "daun", "buah", "batang", "akar", "malai", "bulir"])

    is_numeric_input = clean_msg.isdigit() or clean_msg in []  
    if not is_numeric_input and not has_symptom_word and is_greeting_match:
        return {"intent": "greeting", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    # ==============================================================
    # 7. Pilihan Tombol / Shortcut Interaktif Lainnya
    # ==============================================================
    # Konsultasi Foto
    photo_intent_keywords = [
        "konsultasi foto", "cek foto", "kirim foto", "analisis foto", "diagnosa foto",
        "foto tanaman", "foto daun", "foto buah", "foto penyakit", "foto sakit",
        "mau kirim foto", "bisa kirim foto", "bisa cek foto", "periksa foto",
        "menu_foto", "btn_foto", "btn_konsultasi_foto"
    ]
    if clean_msg in ["2", "2.", "btn_konsultasi_foto", "btn_foto", "menu_foto"] or any(k in clean_msg for k in photo_intent_keywords) or clean_msg in ["foto", "kirim gambar", "upload foto"]:
        return {"intent": "photo_instruction", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    # Riwayat Konsultasi
    history_keywords = ["riwayat", "histori", "rekam jejak", "konsultasi lalu", "konsultasi saya", "riwayat penyakit", "btn_riwayat", "menu_riwayat"]
    if clean_msg in ["6", "6.", "btn_riwayat", "menu_riwayat"] or any(k in clean_msg for k in history_keywords):
        return {"intent": "history", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    # Tanya Penyakit Teks
    disease_prompt_keywords = [
        "tanya penyakit", "konsultasi teks", "konsultasi penyakit", "tanya hama",
        "cek penyakit", "btn_tanya_penyakit", "menu_tanya_penyakit",
        "ceritakan gejala", "ceritakan gejala tanaman lewat teks",
        "tanya hama  penyakit", "tanya hama dan penyakit", "tanya hama & penyakit"
    ]
    is_disease_prompt_match = (
        clean_msg in ["1", "1.", "btn_tanya_penyakit"] or
        any(k in clean_msg for k in disease_prompt_keywords)
    )
    if is_disease_prompt_match and not has_specific_symptom:
        return {"intent": "disease_text_prompt", "crop_context": detected_crop, "is_first_interaction": is_first_time}

    # ==============================================================
    # 8. Diagnosa Hama & Penyakit (Semantic SOP RAG)
    # Default direct routing untuk segala keluhan tanaman cabai & padi
    # ==============================================================
    return {
        "intent": "diagnosis",
        "crop_context": detected_crop,
        "is_first_interaction": is_first_time
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
    """Fitur 1: Menjalankan RAG Semantik untuk 11 Penyakit Tanaman Cabai & Padi dengan Multi-Turn Memory."""
    query = state.get("user_message", "")
    crop_context = state.get("crop_context")
    conversation_history = state.get("conversation_history")

    result = await diagnosis_agent.diagnose_text(
        user_query=query,
        crop_hint=crop_context,
        conversation_history=conversation_history
    )
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
    """Fitur 5: Mengambil data prakiraan cuaca BMKG Adm4 & Open-Meteo serta advisory semprot."""
    query = state.get("user_message", "")

    # 1. Bersihkan tanda baca
    clean_text = re.sub(r"[^\w\s]", " ", query).strip()
    words = clean_text.split()

    # 2. Buang awalan kata administratif
    PREFIX_WORDS = {"desa", "kelurahan", "kecamatan", "kec", "kabupaten", "kab", "kota", "di"}
    while words and words[0].lower() in PREFIX_WORDS:
        words.pop(0)

    location_detail = " ".join(words).title() if words else "Yogyakarta"
    last_word = words[-1].title() if words else "Yogyakarta"

    # Alias & normalisasi nama sentra fokus DIY & Magelang
    CITY_ALIASES = {
        "jogja": "Yogyakarta",
        "yogya": "Yogyakarta",
        "diy": "Yogyakarta",
        "sleman": "Sleman",
        "bantul": "Bantul",
        "kulonprogo": "Kulon Progo",
        "kulon progo": "Kulon Progo",
        "wates": "Wates",
        "garongan": "Garongan",
        "sentolo": "Sentolo",
        "tuksono": "Tuksono",
        "magelang": "Magelang",
        "sawangan": "Sawangan",
        "muntilan": "Muntilan",
        "ngablak": "Ngablak",
        "mertoyudan": "Mertoyudan",
        "pakis": "Pakis",
        "borobudur": "Borobudur",
        "solo": "Surakarta",
        "klaten": "Klaten",
    }

    # Kata-kata yang BUKAN nama lokasi
    NON_LOCATION_WORDS = {
        "cuaca", "hujan", "hari", "besok", "lusa", "sawah", "semprot",
        "penyemprotan", "aman", "bagaimana", "kondisi", "prakiraan",
        "saya", "untuk", "kapan", "bisa", "boleh", "apakah", "ini",
        "petani", "tanaman", "kebun", "lahan", "padi", "cabai",
        "sekarang", "terkini", "update", "info", "tolong", "mohon",
        "gimana", "dong", "yuk", "mau", "dari", "akan"
    }

    loc_alias = None
    query_lower = clean_text.lower()
    for alias, city in CITY_ALIASES.items():
        if alias in query_lower.split() or alias in query_lower:
            loc_alias = city
            break

    # Urutan pemanggilan dengan graceful fallback:
    candidates_to_try = []
    if loc_alias:
        candidates_to_try.append(loc_alias)
    if location_detail and location_detail not in candidates_to_try and location_detail.lower() not in NON_LOCATION_WORDS:
        candidates_to_try.append(location_detail)
    if last_word and last_word not in candidates_to_try and last_word.lower() not in NON_LOCATION_WORDS:
        candidates_to_try.append(last_word)
    if "Yogyakarta" not in candidates_to_try:
        candidates_to_try.append("Yogyakarta")

    result = None
    for loc_candidate in candidates_to_try:
        try:
            res = await weather_service.get_weather_forecast(loc_candidate)
            if res and getattr(res, "lokasi", None):
                result = res
                break
        except Exception as e:
            logger.debug(f"Percobaan cuaca untuk '{loc_candidate}' gagal: {e}")

    # Fallback akhir jika seluruh pemanggilan gagal
    if result is None:
        try:
            result = await weather_service.get_weather_forecast("Yogyakarta")
        except Exception as e:
            logger.error(f"Fallback akhir cuaca Yogyakarta gagal: {e}")
            result = WeatherAdvisoryResult(
                lokasi="Yogyakarta",
                cuaca_saat_ini="Cerah Berawan",
                suhu_celsius=28.0,
                kelembapan_persen=75,
                peluang_hujan_persen=20,
                advisory_penyemprotan="✅ Waktu aman penyemprotan pagi hari pukul 06.30 - 09.00.",
                advisory_pemupukan="✅ Pemupukan kocor aman dilakukan."
            )

    return {"weather_result": result.model_dump() if hasattr(result, "model_dump") else result}


async def fertilizer_node(state: TaniState) -> Dict[str, Any]:
    """Fitur 6: Menghitung dosis dan formulasi pupuk serta pestisida spesifik."""
    query = state.get("user_message", "")
    crop_context = state.get("crop_context")
    result = fertilizer_agent.get_recommendation(query, crop_context)
    return {"fertilizer_result": result.model_dump()}


async def greeting_node(state: TaniState) -> Dict[str, Any]:
    """Pesan perkenalan (chat introduction) ringkas, ramah, dan membumi untuk menyambut petani."""
    welcome_text = (
        "🌿 *Selamat Datang di TaniPintar Bot!*\n"
        "Asisten Sahabat Petani Cerdas untuk Perlindungan Tanaman Cabai & Padi.\n\n"
        "Silakan pilih menu layanan di bawah ini atau ketik pertanyaan Anda:"
    )
    return {"final_response": welcome_text}


async def photo_instruction_node(state: TaniState) -> Dict[str, Any]:
    """Instruksi bagi petani untuk mengirimkan foto tanaman sakit sebelum dianalisis."""
    instruction_text = (
        "📸 *KONSULTASI FOTO TANAMAN (CABAI & PADI)*\n\n"
        "Silakan kirimkan foto daun atau buah tanaman cabai/padi yang sakit. Pastikan foto tidak buram agar bisa saya analisis dengan akurat.\n\n"
        "💡 *Tips Pengambilan Foto:*\n"
        "1. 🔍 *Jarak Dekat:* Fokuskan kamera langsung pada gejala bercak, hama, atau busuk.\n"
        "2. ☀️ *Pencahayaan Baik:* Ambil foto di tempat yang terang dan jelas.\n"
        "3. 📝 *Keterangan (Opsional):* Tambahkan cerita singkat keluhan pada caption foto.\n\n"
        "_Kamera Anda siap? Kirimkan fotonya sekarang ya!_ 🌾"
    )
    return {"final_response": instruction_text}


async def disease_text_prompt_node(state: TaniState) -> Dict[str, Any]:
    """Meminta petani menceritakan gejala penyakit dengan bahasa sehari-hari."""
    prompt_text = (
        "🔬 *KONSULTASI HAMA & PENYAKIT (TEKS)*\n\n"
        "Silakan ceritakan gejala apa yang terlihat pada tanaman Cabai atau Padi Anda menggunakan bahasa sehari-hari.\n\n"
        "📌 *Contoh cerita gejala:*\n"
        "• _'Buah cabai rawit saya ada bercak hitam melingkar membusuk dan rontok'_\n"
        "• _'Daun padi menguning kecoklatan seperti terbakar dari ujung helai'_\n"
        "• _'Banyak kutu putih di balik daun dan daun cabai menggulung keriting'_\n\n"
        "Apa keluhan yang sedang dialami tanaman Anda saat ini? Ceritakan di sini ya! 🌾"
    )
    return {"final_response": prompt_text}


async def price_prompt_node(state: TaniState) -> Dict[str, Any]:
    """Mengarahkan petani memilih komoditas terlebih dahulu untuk cek harga pasar."""
    prompt_text = (
        "💰 *INFORMASI HARGA PASAR HARIAN (DIY & MAGELANG)*\n\n"
        "Bapak/Ibu Petani ingin mengecek harga untuk komoditas apa hari ini?\n\n"
        "1️⃣ *Cabai* (Cabai Rawit Merah, Rawit Hijau, Merah Keriting, Merah Besar)\n"
        "2️⃣ *Padi & Beras* (Gabah Kering Panen/GKP, Beras Medium, Beras Super)\n\n"
        "Silakan pilih tombol di bawah atau ketik pilihan Anda (*Cabai* atau *Padi/Beras*).\n\n"
        "💡 _Tips: Anda juga bisa langsung mengetik misalnya 'Harga cabai di Bantul' atau 'Harga beras di Sleman'._"
    )
    return {"final_response": prompt_text}


async def price_region_prompt_node(state: TaniState) -> Dict[str, Any]:
    """Mengarahkan petani memilih wilayah pasar sentra untuk komoditas terpilih."""
    crop = state.get("crop_context") or "Cabai"
    crop_label = "Cabai (Rawit/Merah)" if "cabai" in crop.lower() else "Padi & Beras"
    prompt_text = (
        f"📍 *PILIH WILAYAH PASAR ({crop_label.upper()})*\n\n"
        f"Untuk memantau harga komoditas *{crop_label}*, silakan sebutkan wilayah pasar Anda:\n\n"
        f"1. *Sleman* (Titik Kumpul Tempel & Pasar Godean)\n"
        f"2. *Bantul* (Pasar Niten & Pasar Imogiri)\n"
        f"3. *Kulon Progo* (Pasar Lelang Garongan/Bugel & Wates)\n"
        f"4. *Kota Yogyakarta* (Pasar Beringharjo & Giwangan)\n"
        f"5. *Magelang* (Pasar Rejowinangun & Lelang Sayur Muntilan/Sawangan)\n\n"
        f"Silakan ketik nama daerah Anda (contoh: *Bantul* atau *Sleman*), atau klik tombol di bawah."
    )
    return {"final_response": prompt_text}


async def weather_prompt_node(state: TaniState) -> Dict[str, Any]:
    """Menanyakan lokasi/desa user untuk menarik data cuaca spesifik tingkat desa/kecamatan."""
    prompt_text = (
        "🌦️ *PREDIKSI CUACA & WAKTU AMAN SEMPROT*\n\n"
        "Bisa sebutkan lokasi sawah, desa, atau kecamatan Anda?\n\n"
        "📌 *Contoh:* _Sleman_, _Bantul_, _Kulon Progo_, _Muntilan_, atau _Sawangan_.\n\n"
        "Saya akan memeriksa prakiraan cuaca, potensi hujan, suhu, dan rekomendasi jam terbaik untuk penyemprotan pestisida hari ini."
    )
    return {"final_response": prompt_text}


async def fertilizer_prompt_node(state: TaniState) -> Dict[str, Any]:
    """Mengarahkan petani menyebutkan komoditas dan fase/kebutuhan dosis pupuk & obat."""
    prompt_text = (
        "🧪 *PANDUAN DOSIS PUPUK & OBAT*\n\n"
        "Bisa sebutkan jenis tanaman (Cabai atau Padi) serta usia/fase tanaman atau keluhan yang ingin ditangani?\n\n"
        "📌 *Contoh:*\n"
        "• _'Dosis pupuk susulan cabai rawit umur 30 HST'_\n"
        "• _'Rekomendasi takaran urea dan NPK untuk padi fase bunting'_\n\n"
        "Saya akan bantu hitungkan takaran dosis anjuran dan cara aplikasi yang tepat dan aman. 🌾"
    )
    return {"final_response": prompt_text}


FOOTER_MENU_HINT = "\n\n💡 Ketik *menu* kapan saja untuk opsi bantuan lain. Ketik *'menu'* kapan saja jika ingin kembali ke halaman utama."


async def format_and_guardrail_node(state: TaniState) -> Dict[str, Any]:
    """Memformat output terstruktur ke WhatsApp Markdown dan menerapkan Guardrail Anti-Halusinasi."""
    if state.get("final_response"):
        return {}

    # Sisipkan banner selamat datang jika ini adalah percakapan pertama kali pengguna (bukan greeting/prompt interaktif)
    is_first = state.get("is_first_interaction", False)
    welcome_banner = ""
    interactive_intents = [
        "greeting", "photo_instruction", "disease_text_prompt",
        "price_prompt", "price_region_prompt", "weather_prompt", "fertilizer_prompt"
    ]
    if is_first and state.get("intent") not in interactive_intents:
        welcome_banner = (
            "🌾 *TaniPintar* — Sahabat Petani Cabai & Padi\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    # 1. Output Fitur 4: Riwayat Konsultasi
    hist = state.get("history_result")
    if hist is not None:
        if not hist:
            msg = (
                "📋 *REKAM JEJAK KONSULTASI PETANI*\n\n"
                "Belum ditemukan riwayat konsultasi untuk nomor WhatsApp ini.\n"
                "Silakan konsultasikan gejala tanaman Cabai atau Padi Anda melalui teks atau foto!"
            )
            return {"final_response": welcome_banner + msg + FOOTER_MENU_HINT}

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
        return {"final_response": welcome_banner + "\n".join(lines) + FOOTER_MENU_HINT}

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
        return {"final_response": welcome_banner + msg + FOOTER_MENU_HINT}

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
        return {"final_response": welcome_banner + msg + FOOTER_MENU_HINT}

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
        return {"final_response": welcome_banner + msg + FOOTER_MENU_HINT}

    # 5. Output Fitur 1 & 2: Diagnosis Teks atau Foto
    diag = state.get("diagnosis_result")
    if diag:
        # Pengecekan Khusus Cabai & Padi
        if not diag.get("is_supported_crop", True):
            return {"final_response": diag.get("unsupported_message") or "Mohon maaf, TaniPintar saat ini khusus melayani tanaman Cabai dan Padi."}

        confidence = diag.get("confidence_score", 0.0)
        rujuk_ppl = diag.get("rujuk_ke_ppl", False)

        # GUARDRAIL AMBANG BATAS: Jika keyakinan sangat rendah (< 35%) atau tidak ada indikasi penyakit
        if confidence < 0.35 and not diag.get("nama_penyakit"):
            logger.info(f"Guardrail aktif: Confidence sangat rendah ({confidence})")
            return {"final_response": welcome_banner + SAFE_FALLBACK_MESSAGE + FOOTER_MENU_HINT}

        langkah = diag.get("langkah_penanganan", {})
        photo_info = "\n📸 _(Analisis Berdasarkan Bukti Foto Lapangan)_" if state.get("media_url") else ""
        
        # Ekstrak informasi Visual RAG & OpenCV
        visual_rag_info = ""
        if diag.get("visual_match_similarity"):
            sim_val = diag.get("visual_match_similarity", 0.0)
            organ_val = (diag.get("cv_organ_detected") or "organ tanaman").capitalize()
            visual_rag_info = (
                f"\n🔍 *Analisis Visual Citra (OpenCV + Visual RAG):*\n"
                f"• Kemiripan Vektor: *{sim_val:.1f}%* terhadap galeri referensi\n"
                f"• Organ Tanaman: *{organ_val}*\n"
            )

        ref_image_url = diag.get("visual_reference_url") or await ConsultationRepository.get_reference_image(diag.get("nama_penyakit", ""))
        ref_section = f"\n\n📷 *Foto Pembanding Referensi (Supabase Storage):*\n{ref_image_url}" if ref_image_url else ""

        # Peringatan PPL jika deskripsi petani singkat/ambigu (tingkat keyakinan moderat)
        ppl_warning = ""
        if confidence < settings.confidence_threshold or rujuk_ppl:
            ppl_warning = (
                f"\n\n⚠️ *Catatan Tingkat Keyakinan Moderat ({int(confidence * 100)}%):*\n"
                f"Karena deskripsi gejala masih singkat/umum, hasil di atas merupakan *dugaan awal yang paling mendekati*. "
                f"Utamakan penanganan fisik/sanitasi terlebih dahulu, dan Anda dapat mengirimkan *foto tanaman yang sakit* "
                f"atau mengonfirmasi ke PPL setempat sebelum aplikasi kimiawi berat."
            )

        msg = (
            f"🌿 *HASIL DIAGNOSIS TANAMAN ({diag.get('nama_tanaman', '').upper()})*{photo_info}\n\n"
            f"🎯 *Indikasi:* {diag.get('nama_penyakit')} "
            f"({diag.get('nama_ilmiah') or 'Patogen'})\n"
            f"🔬 *Penyebab:* {diag.get('penyebab_biologis')}\n"
            f"📊 *Tingkat Keyakinan AI:* {int(confidence * 100)}%\n"
            f"{visual_rag_info}\n"
            f"📝 *Penjelasan Gejala:*\n{diag.get('penjelasan_singkat')}\n\n"
            f"🛠️ *LANGKAH PENANGANAN PRAKTIS (3 PILAR):*\n"
            f"1. *Fisik / Mekanis:*\n   {langkah.get('mekanis')}\n\n"
            f"2. *Sanitasi Lahan & Drainase:*\n   {langkah.get('sanitasi')}\n\n"
            f"3. *Bahan Aktif Kimiawi:*\n   {langkah.get('bahan_aktif_kimiawi') or 'Tidak diperlukan bahan kimiawi.'}\n\n"
            f"⚠️ *Catatan Keselamatan:*\n{diag.get('catatan_keamanan')}"
            f"{ppl_warning}"
            f"{ref_section}\n\n"
            f"_Apabila gejala tidak membaik dalam 3-5 hari, segera hubungi PPL setempat._"
        )
        return {"final_response": welcome_banner + msg + FOOTER_MENU_HINT}

    return {"final_response": welcome_banner + SAFE_FALLBACK_MESSAGE + FOOTER_MENU_HINT}


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

    # Simpan status sesi percakapan dengan current_state posisi menu & timestamp updated_at
    intent = state.get("intent", "main_menu")
    step_map = {
        "greeting": "main_menu",
        "diagnosis": "consultation_completed",
        "vision_diagnosis": "consultation_completed",
        "market_price": "price_view",
        "weather": "weather_view",
        "fertilizer": "fertilizer_view",
        "history": "history_view",
        "photo_instruction": "main_menu",
        "disease_text_prompt": "main_menu",
        "price_prompt": "awaiting_price_commodity",
        "price_region_prompt": "awaiting_price_region",
        "weather_prompt": "main_menu",
        "fertilizer_prompt": "main_menu"
    }
    fallback_step = step_map.get(intent, "main_menu")
    session_st = state.get("session_state") or {"step": fallback_step}
    if not isinstance(session_st, dict):
        session_st = {"step": fallback_step}
    session_st["last_intent"] = intent
    session_st["has_greeted"] = True

    await ConsultationRepository.upsert_session(
        phone_number=phone,
        current_state=session_st,
        last_crop_context=state.get("crop_context")
    )
    return {}


# ==========================================
# WORKFLOW GRAPH CONSTRUCTION
# ==========================================

def route_intent(state: TaniState) -> str:
    """Fungsi conditional routing LangGraph untuk layanan TaniPintar."""
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
    elif intent == "photo_instruction":
        return "photo_instruction"
    elif intent == "disease_text_prompt":
        return "disease_text_prompt"
    elif intent == "price_prompt":
        return "price_prompt"
    elif intent == "price_region_prompt":
        return "price_region_prompt"
    elif intent == "weather_prompt":
        return "weather_prompt"
    elif intent == "fertilizer_prompt":
        return "fertilizer_prompt"
    else:
        return "diagnosis"


def build_tani_graph():
    """Membangun StateGraph LangGraph lengkap untuk Fitur TaniPintar."""
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
    workflow.add_node("photo_instruction", photo_instruction_node)
    workflow.add_node("disease_text_prompt", disease_text_prompt_node)
    workflow.add_node("price_prompt", price_prompt_node)
    workflow.add_node("price_region_prompt", price_region_prompt_node)
    workflow.add_node("weather_prompt", weather_prompt_node)
    workflow.add_node("fertilizer_prompt", fertilizer_prompt_node)
    workflow.add_node("formatter", format_and_guardrail_node)
    workflow.add_node("audit_saver", audit_saver_node)

    # Entrypoint
    workflow.set_entry_point("router")

    # Conditional Edges dari Router ke Seluruh Node Layanan
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
            "photo_instruction": "photo_instruction",
            "disease_text_prompt": "disease_text_prompt",
            "price_prompt": "price_prompt",
            "price_region_prompt": "price_region_prompt",
            "weather_prompt": "weather_prompt",
            "fertilizer_prompt": "fertilizer_prompt",
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
    workflow.add_edge("photo_instruction", "formatter")
    workflow.add_edge("disease_text_prompt", "formatter")
    workflow.add_edge("price_prompt", "formatter")
    workflow.add_edge("price_region_prompt", "formatter")
    workflow.add_edge("weather_prompt", "formatter")
    workflow.add_edge("fertilizer_prompt", "formatter")

    # Formatter lanjut ke audit saver lalu END
    workflow.add_edge("formatter", "audit_saver")
    workflow.add_edge("audit_saver", END)

    return workflow.compile()


# Instance singleton app graph
tani_graph_app = build_tani_graph()
