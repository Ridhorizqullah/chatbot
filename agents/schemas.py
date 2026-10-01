from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import date


class PracticalSteps(BaseModel):
    """Langkah penanganan praktis terstruktur di lapangan."""
    mekanis: str = Field(
        description="Tindakan fisik/mekanis, seperti memotong daun terinfeksi, mencabut tanaman mati, membuang telur hama."
    )
    sanitasi: str = Field(
        description="Langkah kebersihan lingkungan, pembenahan drainase, pengaturan jarak tanam, pembersihan gulma inang."
    )
    bahan_aktif_kimiawi: Optional[str] = Field(
        default=None,
        description="Rekomendasi bahan aktif terdaftar (misal Mankozeb, Abamektin) beserta petunjuk rotasi golongan. Bukan merek dagang."
    )


class DiseaseDiagnosisResult(BaseModel):
    """Skema diagnosis hama dan penyakit tanaman dari PydanticAI (Teks & Foto)."""
    is_supported_crop: bool = Field(
        default=True,
        description="Wajib True jika objek foto/pertanyaan adalah tanaman Cabai atau Padi. Wajib False jika tanaman lain (misal sawit, jagung, apel) atau bukan tanaman."
    )
    unsupported_message: Optional[str] = Field(
        default=None,
        description="Pesan penolakan sopan jika foto/pertanyaan di luar spesialisasi Cabai dan Padi."
    )
    nama_tanaman: Literal["cabai", "padi", "lainnya"] = Field(
        description="Jenis tanaman yang diidentifikasi dari pertanyaan/foto petani."
    )
    nama_penyakit: str = Field(
        description="Nama umum penyakit atau hama (misal: Antraknosa / Patek, Sundep, Hawar Kresek)."
    )
    nama_ilmiah: Optional[str] = Field(
        default=None,
        description="Nama patogen ilmiah (misal: Colletotrichum capsici, Pyricularia oryzae)."
    )
    penyebab_biologis: str = Field(
        description="Kategori penyebab: Jamur, Bakteri, Virus, Hama Serangga, atau Fisiologis."
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Skor keyakinan analisis (0.0 sampai 1.0) berdasarkan kesesuaian visual atau deskripsi dengan literatur 11 penyakit."
    )
    penjelasan_singkat: str = Field(
        description="Penjelasan ramah petani mengapa gejala tersebut mengarah pada penyakit ini."
    )
    langkah_penanganan: PracticalSteps
    rujuk_ke_ppl: bool = Field(
        default=False,
        description="True jika confidence score < 0.70 atau memerlukan verifikasi uji laboratorium lapangan."
    )
    catatan_keamanan: str = Field(
        description="Instruksi keselamatan penting penggunaan Alat Pelindung Diri (APD) dan waktu aplikasi aman."
    )


class CommodityPriceItem(BaseModel):
    """Informasi harga komoditas pangan per wilayah / provinsi."""
    komoditas: str = Field(description="Nama komoditas (Cabai Rawit Merah, Cabai Merah Keriting, Gabah Kering Panen, Beras Medium)")
    provinsi: str = Field(description="Wilayah / Provinsi (misal: Jawa Barat, Jawa Timur, Nasional)")
    harga_petani: int = Field(description="Harga di tingkat produsen/petani (Rp/kg)")
    harga_pasar: int = Field(description="Harga di tingkat pasar grosir/konsumen (Rp/kg)")
    satuan: str = Field(default="kg", description="Satuan takaran (kg)")
    tanggal: str = Field(description="Tanggal acuan data (YYYY-MM-DD)")
    tips_negosiasi: str = Field(description="Tips posisi tawar bagi petani agar tidak dirugikan tengkulak.")


class CommodityPriceResult(BaseModel):
    items: List[CommodityPriceItem]
    catatan_pasar: str
    sumber: str = Field(default="Sistem Otomatis TaniPintar & Panel Pasar Komoditas")


class AdminPriceInputSchema(BaseModel):
    """Skema input harga manual oleh Admin."""
    price_date: date
    commodity: str
    province: str
    farmgate_price: int = Field(gt=0, description="Harga tingkat petani")
    consumer_price: int = Field(gt=0, description="Harga pasar/konsumen")
    notes: Optional[str] = None


class AdminPriceUpdateSchema(BaseModel):
    """Skema update harga pasar oleh Admin."""
    farmgate_price: Optional[int] = Field(default=None, gt=0, description="Harga tingkat petani yang diperbarui")
    consumer_price: Optional[int] = Field(default=None, gt=0, description="Harga pasar/konsumen yang diperbarui")
    notes: Optional[str] = Field(default=None, description="Catatan perubahan")


class AdminAuditFollowUpSchema(BaseModel):
    """Skema update tindak lanjut penanganan rujukan PPL."""
    is_referred_to_ppl: Optional[bool] = Field(default=None, description="Status rujukan PPL")
    followup_notes: Optional[str] = Field(default=None, description="Catatan tindakan dari Petugas Penyuluh Lapangan")



class ConsultationHistoryItem(BaseModel):
    """Item riwayat konsultasi seorang petani."""
    tanggal: str
    tanaman: str
    penyakit_terduga: str
    confidence: str
    status_rujukan: str
    langkah_utama: str
    media_url: Optional[str] = None


class FarmerHistoryResult(BaseModel):
    """Hasil rekap riwayat konsultasi petani."""
    phone_number: str
    total_konsultasi: int
    items: List[ConsultationHistoryItem]
    pesan: str


class WeatherAdvisoryResult(BaseModel):
    """Prakiraan cuaca dan advisory operasional pertanian (penyemprotan & pemupukan)."""
    lokasi: str = Field(description="Nama kota / kabupaten di Indonesia")
    cuaca_saat_ini: str = Field(description="Cerah, Berawan, Hujan Ringan, Hujan Lebat")
    suhu_celsius: float
    kelembapan_persen: int
    peluang_hujan_persen: int
    advisory_penyemprotan: str = Field(
        description="Saran apakah aman menyemprot pestisida hari ini (misal: Aman pagi ini, atau Tunda karena hujan siang nanti)."
    )
    advisory_pemupukan: str = Field(
        description="Saran pemupukan berbasis kondisi kelembapan dan potensi hanyut terbawa air."
    )


class FertilizerRecommendationResult(BaseModel):
    """Rekomendasi takaran pupuk spesifik dan strategi nutrisi tanaman."""
    nama_tanaman: Literal["cabai", "padi"]
    fase_pertumbuhan: str = Field(description="Vegetatif (Tumbuh Daun/Anakan) atau Generatif (Bunga/Buah/Pengisian Bulir)")
    rekomendasi_pupuk: List[str] = Field(description="Daftar jenis dan takaran pupuk per hektar / per tanaman")
    unsur_prioritas: str = Field(description="Unsur hara prioritas (N, P, K, Ca, Mg, Si)")
    pestisida_pendamping: Optional[str] = Field(default=None, description="Bahan aktif pestisida pendamping jika ada gejala serangan")
    catatan_aplikasi: str = Field(description="Cara dan waktu aplikasi pemupukan (kocor, tabur, semprot daun)")
