# 📊 Laporan Progres Rekayasa Sistem: TaniPintar Bot
**Proyek:** TaniPintar — AI WhatsApp Assistant Perlindungan Tanaman Cabai & Padi  
**Tanggal:** 21 Oktober 2026  
**Stack Teknologi:** FastAPI (Python 3.12) • LangGraph • WAHA (WhatsApp HTTP API - GOWS Engine) • Supabase (pgvector & Storage) • Google Gemini Multimodal  

---

## 🧭 Ringkasan Eksekutif

Sprint hari ini menuntaskan 5 pilar utama:
1. **Infrastruktur & Reliability:** Kontainer backend dan WAHA kini terhubung stabil dengan live hot-reload dan healthcheck otomatis.
2. **Pengalaman Pengguna (UX):** Pesan sambutan panjang diganti dengan alur interaktif berbasis tombol (Reply Buttons), panduan foto anti-buram, dan indikator mengetik (*typing presence*).
3. **Conversational State Machine:** Manajemen sesi 30 menit berbasis Supabase dengan fallback navigasi (*keyword escape hatch* dan input angka 1–4).
4. **Keamanan Data (Database Hardening):** 100% temuan Supabase Linter tuntas diperbaiki melalui aktivasi Row Level Security (RLS) dan penguncian fungsi RPC.
5. **Verifikasi Kualitas:** Seluruh 37 skenario pengujian unit dan integrasi lulus 100% (**Green**).

---

## 🛠️ Pencapaian & Rekayasa Teknis

### 1. Stabilisasi Infrastruktur Docker & Live Sync
* **Kendala:** Kontainer backend mengalami *crash loop* saat startup karena dependensi healthcheck WAHA belum siap menerima koneksi.
* **Solusi Teknis:**
  * Menyelaraskan konfigurasi healthcheck `/ping` pada `docker-compose.yml` agar backend hanya aktif setelah WAHA berstatus siap (*healthy*).
  * Mengonfigurasi live volume binding (`./:/app`) dan `uvicorn --reload` sehingga perubahan kode langsung aktif tanpa perlu rebuild kontainer.
* **Hasil:** Waktu iterasi development turun drastis dan kontainer beroperasi tanpa *crash*.

---

### 2. Antarmuka Pesan Interaktif WhatsApp (Reply Buttons, List, & Polling)
* **Kebutuhan:** Menggantikan input teks manual yang rawan *typo* dengan antarmuka native WhatsApp.
* **Solusi Teknis:**
  * Mengimplementasikan `send_buttons_message` pada [services/whatsapp_service.py](file:///e:/wa bot longchain/services/whatsapp_service.py) untuk WAHA `/api/sendButtons` (hingga 4 tombol interaktif) dan Meta Cloud API (3 tombol).
  * Membangun `send_list_message` (menu berseksi) dan `send_poll_message` sebagai opsi fallback interaktif yang paling tahan pembatasan client.
  * Menyiapkan mekanisme *graceful degradation*: jika perangkat pengguna tidak mendukung tombol interaktif, payload otomatis dikonversi menjadi daftar teks bernomor (`1. Opsi A...`).
* **Hasil:** Pengguna dapat memilih menu utama hanya dengan satu ketukan jari.

---

### 3. Redesain Onboarding & UX Percakapan
* **Kondisi Sebelumnya:** Bot mengirim paragraf panjang berisi 6 daftar layanan sekaligus, membuat layar HP pengguna penuh sebelum sempat bertanya.
* **Penyempurnaan:**
  * Menghapus blok teks panjang dan menggantinya dengan sapaan ringkas dan empat tombol tindakan cepat:
    * `[ 🔬 Tanya Penyakit ]`
    * `[ 📷 Konsultasi Foto ]`
    * `[ 💰 Cek Harga Pasar ]`
    * `[ 🌦️ Info Cuaca & Semprot ]`
  * Menambahkan fitur **Pesan Tunggal (Single Payload)**: Sapaan dan tombol dikirim dalam satu pesan untuk mencegah pesan ganda (*double message*).
  * Menambahkan **Typing Presence Indicator** (`/api/startTyping` dan `/api/stopTyping`) agar bot terasa alami saat memproses jawaban.
  * Menambahkan **Quoted Reply (`reply_to`)**: Setiap jawaban bot otomatis mengutip pesan pengguna yang bersangkutan.

---

### 4. Alur Dua Tahap Konsultasi Foto (Vision Pipeline)
* **Tantangan:** Petani sering mengirim foto buram atau kurang fokus, menyebabkan akurasi analisis visual AI menurun.
* **Alur Baru:**
  * **Tahap 1 (Edukasi & Arahan):** Saat menu *"Konsultasi Foto"* dipilih, bot memberi instruksi singkat cara mengambil foto daun/buah yang jelas dengan pencahayaan cukup sebelum meminta file dikirim.
  * **Tahap 2 (Eksekusi Multimodal Real-Time):** Setelah foto masuk (`media_id` terbaca):
    1. Filter ketajaman citra dengan OpenCV Laplacian Variance.
    2. Pencarian kemiripan visual terhadap 72 galeri penyakit pada Supabase Vector Storage.
    3. Penarikan SOP resmi Kementan via RAG.
    4. Diagnosa akhir dan rekomendasi praktis 3 pilar (Mekanis, Sanitasi, Kimiawi) oleh Gemini Vision.

---

### 5. Manajemen Sesi 30 Menit & Navigasi Hybrid
* **Implementasi:** Tabel `user_sessions` pada Supabase mencatat nomor telepon, riwayat konteks tanaman (`cabai` / `padi`), posisi alur (*step*), dan *timestamp* terakhir.
* **Fitur Utama:**
  * **Auto-Reset 30 Menit:** Jika pengguna tidak merespons selama >30 menit, sesi kembali ke menu utama secara otomatis.
  * **Navigasi Hybrid (Menu + Angka + Teks):** Pengguna bisa menekan tombol, mengetik angka `1–4`, atau langsung mengetik pertanyaan bebas (misal: *"harga cabai di bantul"*).
  * **Global Escape Hatch:** Kata kunci seperti `menu`, `batal`, `mulai`, atau `reset` langsung mengembalikan pengguna ke menu awal tanpa *stuck*.
  * **Footer Hint:** Menampilkan petunjuk navigasi ringkas di akhir pesan panjang: `💡 Ketik 'menu' untuk kembali ke pilihan utama.`

---

### 6. Penguatan Keamanan Database (Supabase Linter Fix)
* **Temuan Awal:** Seluruh tabel publik belum menerapkan Row Level Security (RLS ERROR), serta fungsi RPC memiliki *mutable search_path*.
* **Tindakan Perbaikan:**
  * Mengaktifkan RLS pada seluruh tabel: `user_sessions`, `consultation_audits`, `market_prices`, `knowledge_base`, `disease_reference_images`, dan `disease_image_gallery`.
  * Menerapkan kebijakan isolasi data:
    * Tabel audit dan sesi percakapan dibatasi khusus untuk backend (`service_role`).
    * Tabel referensi publik (harga pasar dan basis pengetahuan penyakit) dibuka akses baca publik (`SELECT`) dengan hak tulis khusus `service_role`.
  * Mengunci `search_path = public` dan menyetel `SECURITY INVOKER` pada fungsi RPC pencocokan vektor.
* **Hasil:** Status audit Supabase Linter tuntas 100% (**0 Error, 0 Warning**).

---

## 🧪 Hasil Pengujian Sistem (Test Suite)

Pengujian komprehensif dijalankan pada backend Python 3.12:

| Modul Uji | Komponen yang Diverifikasi | Jumlah Kasus | Hasil |
| :--- | :--- | :---: | :---: |
| `tests/test_interactive_messages.py` | Reply buttons, list message, polling, single welcome payload, quoted reply, typing presence, routing angka 1–4 | 16 | **100% PASSED** |
| `tests/test_session_management.py` | Global reset keywords, evaluasi timeout 30 menit, pemulihan sesi, footer hint | 5 | **100% PASSED** |
| `tests/test_api_endpoints.py` | Verifikasi signature HMAC WAHA, handshake Meta, router payload, latency monitor | 9 | **100% PASSED** |
| `tests/test_tani_pintar.py` | Guardrail anti-halusinasi, router intent multi-turn, integrasi cuaca BMKG, fallback | 7 | **100% PASSED** |
| **TOTAL** | **Seluruh Arsitektur Bot TaniPintar** | **37 Kasus** | **100% PASSED** |

---

## 📌 Ringkasan Singkat untuk Update Dosen / Tim (Siap Salin)

> **Update Progres TaniPintar Bot — 21 Oktober 2026**
>
> 1. **UX Percakapan Modern:** Menu panjang berbasis teks kini diganti dengan WhatsApp Reply Buttons (4 menu utama) dan alur interaktif dua tahap untuk konsultasi foto penyakit tanaman.
> 2. **Session State & Resilience:** Ditambahkan tabel `user_sessions` di Supabase dengan auto-timeout 30 menit, dukungan input angka 1–4, serta kata kunci `menu`/`batal` agar pengguna tidak tersesat.
> 3. **Chat Polish:** Respon kini dilengkapi Quoted Reply (`reply_to`), indikator *typing*, dan pesan tunggal agar tidak terjadi *double message*.
> 4. **Keamanan Database:** Semua celah RLS dan fungsi RPC Supabase sudah diperbaiki (100% lulus audit Supabase Linter).
> 5. **Quality Assurance:** 37 pengujian otomatis lulus 100% (unit test & integration test).
>
> Sistem siap untuk sesi demo dan uji coba lapangan.
