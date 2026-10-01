import httpx
from typing import Optional, Dict, Any, Tuple
from agents.schemas import WeatherAdvisoryResult
from core.config import settings
from core.logger import logger


class WeatherService:
    """Service prakiraan cuaca pertanian menggunakan WeatherAPI.com dengan fallback ke Open-Meteo API."""

    # Koordinat fallback untuk sentra pertanian utama Indonesia (untuk Open-Meteo)
    DEFAULT_COORDINATES = {
        "karawang": (-6.3060, 107.3019),
        "brebes": (-6.8703, 109.0436),
        "kediri": (-7.8166, 112.0119),
        "malang": (-7.9839, 112.6214),
        "bandung": (-6.9175, 107.6191),
        "garut": (-7.2279, 107.9086),
        "subang": (-6.5686, 107.7600),
        "indramayu": (-6.3264, 108.3200),
        "boyolali": (-7.5361, 110.5947),
        "medan": (3.5952, 98.6722),
        "makassar": (-5.1477, 119.4327),
        "jakarta": (-6.2088, 106.8456)
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

    async def _get_weatherapi_forecast(self, location_query: str) -> Optional[WeatherAdvisoryResult]:
        """Mengambil data cuaca akurat dari WeatherAPI.com."""
        api_key = settings.weather_api_key
        if not api_key:
            return None

        # Bersihkan nama lokasi
        loc_clean = location_query.replace("?", "").replace("di", "").strip() or "Karawang"
        url = f"https://api.weatherapi.com/v1/forecast.json?key={api_key}&q={loc_clean}&days=1&lang=id"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code != 200:
                    logger.warning(f"WeatherAPI.com returned status {res.status_code}: {res.text}")
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

            # Hitung peluang hujan harian
            rain_chance = 20
            forecastday = data.get("forecast", {}).get("forecastday", [])
            if forecastday:
                day_data = forecastday[0].get("day", {})
                rain_chance = int(day_data.get("daily_chance_of_rain", 20))

            spray_advice, fert_advice = self._build_advisories(precip, rain_chance, humidity)

            logger.info(f"Berhasil mengambil data cuaca dari WeatherAPI.com untuk {resolved_name}")
            return WeatherAdvisoryResult(
                lokasi=resolved_name,
                cuaca_saat_ini=condition_text,
                suhu_celsius=temp,
                kelembapan_persen=humidity,
                peluang_hujan_persen=rain_chance,
                advisory_penyemprotan=spray_advice,
                advisory_pemupukan=fert_advice
            )
        except Exception as e:
            logger.warning(f"Gagal mengambil cuaca WeatherAPI.com: {e}")
            return None

    async def get_coordinates_for_location(self, location_name: str) -> Optional[tuple[float, float, str]]:
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

        return (-6.3060, 107.3019, "Karawang (Default Sentra Padi)")

    async def get_weather_forecast(self, location_query: str = "Karawang") -> WeatherAdvisoryResult:
        """Mengambil data cuaca terkini menggunakan WeatherAPI.com dengan fallback ke Open-Meteo."""
        # 1. Coba WeatherAPI.com terlebih dahulu
        result = await self._get_weatherapi_forecast(location_query)
        if result:
            return result

        # 2. Fallback ke Open-Meteo jika WeatherAPI gagal atau key belum diset
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
            async with httpx.AsyncClient(timeout=10.0) as client:
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
                lokasi=resolved_name,
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
                lokasi=resolved_name,
                cuaca_saat_ini="Cerah Berawan (Estimasi)",
                suhu_celsius=29.0,
                kelembapan_persen=78,
                peluang_hujan_persen=25,
                advisory_penyemprotan="✅ Cuaca diperkirakan cukup aman untuk penyemprotan pada pagi hari.",
                advisory_pemupukan="✅ Aplikasi pemupukan dapat dilakukan sesuai jadwal rutin pemeliharaan."
            )

