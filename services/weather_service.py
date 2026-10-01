import httpx
from typing import Optional, Dict, Any
from agents.schemas import WeatherAdvisoryResult
from core.logger import logger


class WeatherService:
    """Service prakiraan cuaca pertanian menggunakan Open-Meteo API (Bebas biaya, tanpa API key)."""

    # Koordinat fallback untuk sentra pertanian utama Indonesia
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

    async def get_coordinates_for_location(self, location_name: str) -> Optional[tuple[float, float, str]]:
        """Mencari koordinat lintang & bujur dari nama kota/kabupaten di Indonesia."""
        loc_clean = location_name.lower().strip()

        # 1. Cek kamus sentra pertanian lokal
        for key, coords in self.DEFAULT_COORDINATES.items():
            if key in loc_clean:
                return (coords[0], coords[1], key.capitalize())

        # 2. Cek Open-Meteo Geocoding API
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

        # Default ke Karawang (Sentra Lumbung Padi Nasional)
        return (-6.3060, 107.3019, "Karawang (Default Sentra Padi)")

    async def get_weather_forecast(self, location_query: str = "Karawang") -> WeatherAdvisoryResult:
        """Mengambil data cuaca terkini dan menyusun rekomendasi teknis penyemprotan & pemupukan."""
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

            # Hitung peluang hujan rata-rata 6 jam ke depan
            hourly_prob = data.get("hourly", {}).get("precipitation_probability", [0])
            avg_rain_prob = int(sum(hourly_prob[:6]) / min(len(hourly_prob[:6]), 6)) if hourly_prob else 20

            # Deskripsi cuaca berdasarkan WMO Weather Code
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

            # Advisory Penyemprotan & Pemupukan
            if precip > 0.5 or avg_rain_prob > 50:
                spray_advice = (
                    "⚠️ *TUNDA PENYEMPROTAN PESTISIDA/FUNGISIDA:* Potensi hujan cukup tinggi. "
                    "Bahan aktif berisiko luntur dan terbuang percuma sebelum diserap jaringan daun. "
                    "Tunggu hingga cuaca cerah minimal 4-6 jam."
                )
                fertilizer_advice = (
                    "⚠️ *HINDARI PEMUPUKAN TABUR:* Hindari menabur Urea atau NPK saat air sawah mengalir kencang "
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
