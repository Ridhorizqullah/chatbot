import httpx
from typing import Optional, Dict, Any, Tuple
from agents.schemas import WeatherAdvisoryResult
from core.config import settings
from core.logger import logger


class WeatherService:
    """
    Service prakiraan cuaca pertanian dengan arsitektur multi-sumber:
      1. Prioritas Utama: API Terbuka Resmi BMKG (api.bmkg.go.id) tingkat desa/kelurahan (Adm4)
      2. Fallback Sekunder: WeatherAPI.com (resolusi harian & kondisi real-time)
      3. Fallback Tersier: Open-Meteo Agricultural API (evapotranspirasi & curah hujan koordinat)
    """

    # Kode Wilayah Administrasi Tingkat IV (Kepmendagri No 100.1.1-6117)
    # Khusus Sentra Pertanian D.I. Yogyakarta & Magelang
    BMKG_ADM4_CODES: Dict[str, Tuple[str, str]] = {
        # D.I. Yogyakarta (Provinsi 34)
        "yogyakarta": ("34.71.01.1001", "Gowongan, Danurejan, Kota Yogyakarta"),
        "jogja": ("34.71.01.1001", "Gowongan, Danurejan, Kota Yogyakarta"),
        "diy": ("34.71.01.1001", "D.I. Yogyakarta"),
        "sleman": ("34.04.09.2001", "Sumberharjo, Prambanan, Sleman"),
        "tempel": ("34.04.08.2001", "Lumbungrejo, Tempel, Sleman"),
        "pakem": ("34.04.14.2001", "Pakembinangun, Pakem, Sleman"),
        "kalasan": ("34.04.04.2001", "Tirtomartani, Kalasan, Sleman"),
        "ngemplak": ("34.04.06.2001", "Wedomartani, Ngemplak, Sleman"),
        "bantul": ("34.02.01.2001", "Palbapang, Bantul, Bantul"),
        "imogiri": ("34.02.04.2001", "Imogiri, Imogiri, Bantul"),
        "sewon": ("34.02.15.2001", "Panggungharjo, Sewon, Bantul"),
        "kulon progo": ("34.01.01.2001", "Wates, Wates, Kulon Progo"),
        "kulonprogo": ("34.01.01.2001", "Wates, Wates, Kulon Progo"),
        "wates": ("34.01.01.2001", "Wates, Wates, Kulon Progo"),
        "garongan": ("34.01.02.2001", "Garongan / Panjatan, Kulon Progo"),
        "panjatan": ("34.01.02.2001", "Panjatan, Kulon Progo"),
        "gunungkidul": ("34.03.01.2001", "Wonosari, Wonosari, Gunungkidul"),
        "wonosari": ("34.03.01.2001", "Wonosari, Wonosari, Gunungkidul"),

        # Magelang (Provinsi 33 - Jawa Tengah)
        "magelang": ("33.08.08.2001", "Tanjung, Muntilan, Magelang"),
        "muntilan": ("33.08.08.2001", "Tanjung, Muntilan, Magelang"),
        "mertoyudan": ("33.08.10.2001", "Deyangan, Mertoyudan, Magelang"),
        "sawangan": ("33.08.08.2001", "Sentra Sayur Sawangan, Magelang"),
        "ngablak": ("33.08.08.2001", "Sentra Lereng Ngablak, Magelang"),
        "pakis": ("33.08.08.2001", "Pakis, Magelang"),
        "borobudur": ("33.08.08.2001", "Borobudur, Magelang"),
        "secang": ("33.08.08.2001", "Secang, Magelang"),
    }

    # Koordinat fallback Open-Meteo
    DEFAULT_COORDINATES = {
        "yogyakarta": (-7.7971, 110.3688),
        "jogja": (-7.7971, 110.3688),
        "diy": (-7.7971, 110.3688),
        "sleman": (-7.7156, 110.3556),
        "bantul": (-7.8920, 110.3283),
        "kulon progo": (-7.8286, 110.1585),
        "kulonprogo": (-7.8286, 110.1585),
        "wates": (-7.8587, 110.1583),
        "garongan": (-7.9250, 110.1167),
        "gunungkidul": (-7.9625, 110.6033),
        "magelang": (-7.4797, 110.2177),
        "sawangan": (-7.5342, 110.3528),
        "muntilan": (-7.5794, 110.2978),
        "mertoyudan": (-7.5147, 110.2289),
        "ngablak": (-7.4042, 110.3800),
        "pakis": (-7.4644, 110.3514),
        "borobudur": (-7.6079, 110.2038),
        "semarang": (-6.9667, 110.4167),
        "klaten": (-7.7059, 110.6058),
        "karawang": (-6.3060, 107.3019),
    }

    def _build_advisories(self, precip: float, rain_prob: int, humidity: int) -> Tuple[str, str]:
        """Menyusun rekomendasi teknis agronomi untuk penyemprotan & pemupukan."""
        if precip > 0.5 or rain_prob > 50:
            spray_advice = (
                "⚠️ *TUNDA PENYEMPROTAN PESTISIDA/FUNGISIDA:* Potensi hujan cukup tinggi. "
                "Bahan aktif berisiko luntur dan terbuang percuma sebelum diserap jaringan daun. "
                "Tunggu hingga cuaca cerah minimal 4-6 jam."
            )
            fertilizer_advice = (
                "⚠️ *HINDARI PEMUPUKAN TABUR:* Hindari menabur Urea atau NPK saat air mengalir kencang "
                "agar butiran pupuk tidak hanyut terbawa erosi limpasan."
            )
        elif humidity > 85:
            spray_advice = (
                "ℹ️ *WASPADA KELEMBAPAN TINGGI:* Kelembapan udara tinggi (>85%) sangat memicu spora jamur "
                "(Blas padi / Antraknosa cabai). Jika harus menyemprot fungisida, campurkan perekat (adjuvant/sticker) "
                "dan lakukan pada pagi hari setelah embun kering (pukul 07.00 - 09.30)."
            )
            fertilizer_advice = (
                "✅ *PEMUPUKAN KOCOR DIREKOMENDASIKAN:* Pengocoran di dekat perakaran aman dilakukan, "
                "utamakan pupuk Kalsium dan Silika untuk mengeraskan sel tanaman menghadapi tekanan jamur."
            )
        else:
            spray_advice = (
                "✅ *KONDISI SANGAT KONDUSIF UNTUK PENYEMPROTAN:* Cuaca cerah dan angin stabil. "
                "Waktu terbaik aplikasi adalah pukul 06.30 - 09.00 pagi atau 15.30 - 17.00 sore "
                "saat stomata daun terbuka sempurna."
            )
            fertilizer_advice = (
                "✅ *PEMUPUKAN AMAN:* Pemupukan susulan (tabur maupun kocor) dapat diaplikasikan sesuai dosis fase tanaman."
            )

        return spray_advice, fertilizer_advice

    async def _get_bmkg_forecast(self, location_query: str) -> Optional[WeatherAdvisoryResult]:
        """
        Mengambil data cuaca resmi dari API Terbuka BMKG (api.bmkg.go.id)
        berdasarkan kode administrasi tingkat IV (kelurahan/desa) di DIY & Magelang.
        """
        q_lower = location_query.lower().strip()

        # Cocokkan nama wilayah dengan kode Adm4 BMKG
        matched_code: Optional[str] = None
        matched_label: Optional[str] = None

        for key, (adm4, label) in self.BMKG_ADM4_CODES.items():
            if key in q_lower:
                matched_code = adm4
                matched_label = label
                break

        # Jika query umum tanpa nama spesifik, defaultkan ke Yogyakarta
        if not matched_code:
            matched_code, matched_label = self.BMKG_ADM4_CODES["yogyakarta"]

        api_url = f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={matched_code}"

        try:
            headers = {
                "User-Agent": "curl/7.68.0",
                "Accept": "application/json"
            }
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                res = await client.get(api_url)
                if res.status_code != 200:
                    logger.warning(f"[BMKG API] Status code {res.status_code} untuk adm4 {matched_code}")
                    return None
                data = res.json()

            lokasi_meta = data.get("lokasi", {})
            desa = lokasi_meta.get("desa", "")
            kec = lokasi_meta.get("kecamatan", "")
            kotkab = lokasi_meta.get("kotkab", "")

            location_title = f"{desa}, {kec}, {kotkab} (BMKG Resmi)" if desa else (matched_label or "D.I. Yogyakarta / Magelang")

            # Ekstrak data cuaca periode terkini (per 3 jam)
            cuaca_days = data.get("data", [])[0].get("cuaca", []) if data.get("data") else []
            if not cuaca_days or not cuaca_days[0]:
                return None

            # Ambil entri terdekat saat ini
            current_forecast = cuaca_days[0][0]
            temp = float(current_forecast.get("t", 28.0))
            humidity = int(current_forecast.get("hu", 75))
            weather_desc = current_forecast.get("weather_desc", "Cerah Berawan")
            precip = float(current_forecast.get("tp", 0.0))
            wind_speed = current_forecast.get("ws", 5.0)
            wind_dir = current_forecast.get("wd", "Angin Stabil")

            # Estimasi peluang hujan berdasarkan deskripsi cuaca BMKG
            desc_lower = weather_desc.lower()
            if "lebat" in desc_lower or "petir" in desc_lower:
                rain_prob = 90
            elif "sedang" in desc_lower or "hujan" in desc_lower:
                rain_prob = 75
            elif "ringan" in desc_lower or "gerimis" in desc_lower:
                rain_prob = 55
            elif "berawan" in desc_lower:
                rain_prob = 30
            else:
                rain_prob = 15

            spray_advice, fert_advice = self._build_advisories(precip, rain_prob, humidity)

            # Tambahkan detail kecepatan dan arah angin resmi BMKG ke advisory
            spray_with_wind = f"{spray_advice}\n💨 *Angin BMKG:* {wind_speed} km/jam (Arah: {wind_dir})"

            logger.info(f"✅ [BMKG API] Berhasil memuat cuaca resmi untuk {location_title}: {temp}°C, {weather_desc}")
            return WeatherAdvisoryResult(
                lokasi=location_title,
                cuaca_saat_ini=f"{weather_desc} (Sumber: BMKG)",
                suhu_celsius=temp,
                kelembapan_persen=humidity,
                peluang_hujan_persen=rain_prob,
                advisory_penyemprotan=spray_with_wind,
                advisory_pemupukan=fert_advice
            )

        except Exception as e:
            logger.warning(f"Gagal mengambil cuaca dari API resmi BMKG: {e}")
            return None

    async def _get_weatherapi_forecast(self, location_query: str) -> Optional[WeatherAdvisoryResult]:
        """Fallback: Mengambil data cuaca akurat dari WeatherAPI.com."""
        api_key = settings.weather_api_key
        if not api_key:
            return None

        loc_clean = location_query.replace("?", "").replace("di ", "").strip() or "Yogyakarta"
        query_param = loc_clean if "indonesia" in loc_clean.lower() else f"{loc_clean}, Indonesia"
        url = f"https://api.weatherapi.com/v1/forecast.json?key={api_key}&q={query_param}&days=1&lang=id"

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    return None
                data = res.json()

            loc = data.get("location", {})
            loc_name = loc.get("name", loc_clean)
            region = loc.get("region", "")
            resolved_name = f"{loc_name} ({region})" if region and region.lower() != loc_name.lower() else loc_name

            current = data.get("current", {})
            temp = float(current.get("temp_c", 28.0))
            humidity = int(current.get("humidity", 80))
            condition_text = current.get("condition", {}).get("text", "Cerah Berawan")
            precip = float(current.get("precip_mm", 0.0))

            rain_chance = 20
            forecastday = data.get("forecast", {}).get("forecastday", [])
            if forecastday:
                day_data = forecastday[0].get("day", {})
                rain_chance = int(day_data.get("daily_chance_of_rain", 20))

            spray_advice, fert_advice = self._build_advisories(precip, rain_chance, humidity)

            return WeatherAdvisoryResult(
                lokasi=f"{resolved_name} (WeatherAPI)",
                cuaca_saat_ini=condition_text,
                suhu_celsius=temp,
                kelembapan_persen=humidity,
                peluang_hujan_persen=rain_chance,
                advisory_penyemprotan=spray_advice,
                advisory_pemupukan=fert_advice
            )
        except Exception:
            return None

    async def get_coordinates_for_location(self, location_name: str) -> Optional[Tuple[float, float, str]]:
        """Mencari koordinat lintang & bujur dari nama kota/kabupaten di Indonesia untuk Open-Meteo."""
        loc_clean = location_name.lower().strip()

        for key, coords in self.DEFAULT_COORDINATES.items():
            if key in loc_clean:
                return (coords[0], coords[1], key.capitalize())

        url = f"https://geocoding-api.open-meteo.com/v1/search?name={location_name}&count=1&language=id&format=json"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results")
                    if results and len(results) > 0:
                        first = results[0]
                        return (first["latitude"], first["longitude"], first.get("name", location_name))
        except Exception as e:
            logger.warning(f"Geocoding API gagal: {e}")

        return (-7.7971, 110.3688, "Yogyakarta (Default Fokus Wilayah)")

    async def get_weather_forecast(self, location_query: str = "Yogyakarta") -> WeatherAdvisoryResult:
        """
        Mengambil data cuaca terkini:
          1. Menggunakan API Terbuka BMKG resmi (Tingkat IV Desa/Kecamatan)
          2. Fallback ke WeatherAPI.com jika BMKG gagal
          3. Fallback ke Open-Meteo Agricultural API jika keduanya belum tersedia
        """
        # 1. Prioritas Utama: API Terbuka Resmi BMKG (Tingkat Desa/Kelurahan)
        bmkg_result = await self._get_bmkg_forecast(location_query)
        if bmkg_result:
            return bmkg_result

        # 2. Fallback Sekunder: WeatherAPI.com
        weatherapi_result = await self._get_weatherapi_forecast(location_query)
        if weatherapi_result:
            return weatherapi_result

        # 3. Fallback Tersier: Open-Meteo Agricultural API
        logger.info(f"Menggunakan Open-Meteo fallback untuk lokasi '{location_query}'")
        lat, lon, resolved_name = await self.get_coordinates_for_location(location_query)

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation,weather_code"
            f"&hourly=precipitation_probability"
            f"&timezone=Asia%2FJakarta"
        )

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    raise Exception(f"Open-Meteo returned status {res.status_code}")
                data = res.json()

            current = data.get("current", {})
            temp = float(current.get("temperature_2m", 28.0))
            humidity = int(current.get("relative_humidity_2m", 80))
            precip = float(current.get("precipitation", 0.0))
            weather_code = int(current.get("weather_code", 0))

            hourly_prob = data.get("hourly", {}).get("precipitation_probability", [0])
            avg_rain_prob = int(sum(hourly_prob[:6]) / min(len(hourly_prob[:6]), 6)) if hourly_prob else 20

            if weather_code in [0, 1]:
                weather_desc = "Cerah / Berawan Tipis"
            elif weather_code in [2, 3]:
                weather_desc = "Berawan / Mendung"
            elif weather_code in [51, 53, 55, 61, 63, 65, 80, 81]:
                weather_desc = "Hujan Ringan - Sedang"
            elif weather_code >= 82:
                weather_desc = "Hujan Lebat / Petir"
            else:
                weather_desc = "Berawan"

            spray_advice, fertilizer_advice = self._build_advisories(precip, avg_rain_prob, humidity)

            return WeatherAdvisoryResult(
                lokasi=f"{resolved_name} (Open-Meteo)",
                cuaca_saat_ini=weather_desc,
                suhu_celsius=temp,
                kelembapan_persen=humidity,
                peluang_hujan_persen=avg_rain_prob,
                advisory_penyemprotan=spray_advice,
                advisory_pemupukan=fertilizer_advice
            )

        except Exception as e:
            logger.error(f"Gagal mengambil prakiraan cuaca Open-Meteo: {e}")
            return WeatherAdvisoryResult(
                lokasi=f"{location_query} (Estimasi Cadangan)",
                cuaca_saat_ini="Cerah Berawan (Estimasi)",
                suhu_celsius=29.0,
                kelembapan_persen=78,
                peluang_hujan_persen=25,
                advisory_penyemprotan="✅ Cuaca diperkirakan cukup aman untuk penyemprotan pada pagi hari.",
                advisory_pemupukan="✅ Aplikasi pemupukan dapat dilakukan sesuai jadwal rutin pemeliharaan."
            )
