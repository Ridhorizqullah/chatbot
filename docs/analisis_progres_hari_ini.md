# 📊 Laporan Rekayasa & Progres Sistem: TaniPintar Bot
**Proyek:** TaniPintar — AI WhatsApp Assistant Perlindungan Tanaman Cabai & Padi  
**Tanggal Update:** 22 Oktober 2026  
**Status Sesi:** Production-Ready & Feature-Complete  
**Stack Teknologi:** FastAPI (Python 3.12) • LangGraph • WAHA (WhatsApp HTTP API - GOWS Engine) • Supabase (pgvector & Storage) • Google Gemini Multimodal • OpenCV (Laplacian Filter) • BMKG API & WeatherAPI  

---

## 🧭 Ringkasan Eksekutif Pembaruan Hari Ini

Pada pembaruan hari ini (**22 Oktober 2026** / commit `fad54a7`), sistem **TaniPintar Bot** telah ditingkatkan secara masif melalui integrasi antarmuka interaktif native WhatsApp, alur percakapan terpandu (*guided conversational state machine*), memori percakapan multi-turn, penguatan keamanan database (RLS), hingga perluasan test suite otomatis.

### 🌟 7 Pilar Utama yang Telah Dimasukkan:
1. **Alur Interaktif Dua Tahap Cek Harga Pasar (Interactive Market Price Flow):** Navigasi pemilihan komoditas (Cabai vs Padi & Beras) lalu pemilihan wilayah pasar sentra (Sleman, Bantul, Kulon Progo, Yogyakarta, Magelang) berbasis tombol/list interaktif.
2. **Penyempurnaan Routing Cuaca & Rekomendasi Jam Semprot:** Perbaikan *routing keyword* wilayah (seperti *"bantul"*) langsung masuk ke intent cuaca tanpa mental ke menu utama, ditambah fitur agronomis *"Waktu Aman Semprot"*.
3. **Memori Percakapan Beruntun (Multi-Turn Conversation History):** Bot kini mengingat riwayat interaksi sebelumnya melalui database Supabase, didukung standardisasi embedding `gemini-embedding-001` (768 dimensi).
4. **Antarmuka WhatsApp Interaktif Lengkap (Buttons, Lists, Polls, & Typing):** Integrasi penuh `send_buttons_message`, `send_list_message`, `send_poll_message`, *typing presence indicator*, dan *quoted reply* (`reply_to`).
5. **Session Management & Resilience 30 Menit:** Auto-timeout sesi inaktif >30 menit, navigasi angka cepat (`1–4`), serta *Global Escape Hatch* (`menu`, `batal`, `mulai`, `reset`).
6. **Patch Keamanan Database & Audit Linter (100% Resolved):** File `database/schema_patch.sql` mengaktifkan Row Level Security (RLS) pada 6 tabel dan mengunci `search_path = public` pada fungsi RPC vector search.
7. **Ekspansi Test Suite Otomatis:** Penambahan modul pengujian baru `test_price_interactive_flow.py` dan `test_weather_routing_flow.py` untuk menjamin keandalan seluruh alur baru.

---

## 📋 Rincian Detail Seluruh Komponen yang Dimasukkan

```
┌────────────────────────────────────────────────────────────────────────┐
│                      ARSITEKTUR PEMBARUAN SISTEM                       │
└────────────────────────────────────────────────────────────────────────┘
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
[ WhatsApp Interface ]     [ Conversational State ]     [ Database & AI ]
 • Reply Buttons (4 opsi)   • Multi-Step Price Flow      • RLS 6 Tabel Utama
 • Interactive List/Menu    • Quick Action Semprot       • Function search_path
 • Typing Presence          • Multi-Turn Memory          • Gemini 768-dim Embed
 • Quoted Reply (reply_to)  • 30-Min Auto Timeout        • 72 Vektor Visual RAG
 • Single Onboarding Msg    • Global Escape Hatch        • Fallback Weather BMKG
```

---

### 1. 💰 Alur Interaktif Dua Tahap Cek Harga Pasar (*Interactive Market Price Flow*)
* **File Terkait:** [graph_builder.py](file:///e:/wa bot longchain/graph_builder.py), [services/price_service.py](file:///e:/wa bot longchain/services/price_service.py), [database/repository.py](file:///e:/wa bot longchain/database/repository.py), [tests/test_price_interactive_flow.py](file:///e:/wa bot longchain/tests/test_price_interactive_flow.py)
* **Kebutuhan Masalah:** Sebelumnya petani harus mengetik nama komoditas dan daerah secara manual dalam satu kalimat panjang. Kesalahan pengetikan (*typo*) sering membuat pencarian harga gagal.
* **Solusi & Logika Baru yang Diimplementasikan:**
  1. **Tahap 1 — Pemilihan Komoditas (`awaiting_price_commodity`):**
     * Saat user menekan tombol `[ 💰 Cek Harga Pasar ]` atau mengetik `3`, bot menanyakan komoditas yang ingin dipantau dengan tombol:
       * `[ 🌶️ Cabai (Rawit/Merah) ]`
       * `[ 🌾 Padi & Beras ]`
  2. **Tahap 2 — Pemilihan Wilayah Pasar Sentra (`awaiting_price_region`):**
     * Setelah komoditas dipilih, bot menyimpan konteks komoditas ke sesi dan menyajikan pilihan pasar sentra:
       * 1. Sleman (Titik Kumpul Tempel & Pasar Godean)
       * 2. Bantul (Pasar Niten & Pasar Imogiri)
       * 3. Kulon Progo (Pasar Lelang Garongan/Bugel & Wates)
       * 4. Kota Yogyakarta (Pasar Beringharjo & Giwangan)
       * 5. Magelang (Pasar Rejowinangun & Lelang Sayur Muntilan)
  3. **Tahap 3 — Kartu Ringkasan Harga:**
     * Menampilkan perbandingan harga tingkat petani (*farmgate*) vs harga konsumen, tren pergerakan harga, tanggal pantauan terbaru, serta sumber resmi (Bapanas, Disperindag, Pasar Lelang).
  4. **Direct Bypass Tetap Aktif:**
     * Petani yang sudah mahir tetap bisa langsung mengetik *"harga cabai di bantul"* dan bot langsung menampilkan kartu harga tanpa harus melewati tahapan menu.

---

### 2. 🌦️ Perbaikan Routing Cuaca & Rekomendasi Waktu Aman Semprot
* **File Terkait:** [graph_builder.py](file:///e:/wa bot longchain/graph_builder.py), [services/weather_service.py](file:///e:/wa bot longchain/services/weather_service.py), [tests/test_weather_routing_flow.py](file:///e:/wa bot longchain/tests/test_weather_routing_flow.py)
* **Penyempurnaan Routing:**
  * Memperbaiki bug di mana pengetikan nama daerah langsung seperti *"bantul"*, *"sleman"*, *"kulon progo"* sebelumnya mental atau disangka kata sapaan (*greeting*).
  * Menghubungkan input nama lokasi langsung ke query cuaca mikro BMKG tingkat kelurahan/kecamatan (Adm4) atau pasar pertanian.
* **Fitur Agronomis "Waktu Aman Semprot":**
  * Evaluasi otomatis apakah kondisi cuaca saat ini aman untuk penyemprotan fungisida/pestisida:
    * Kecepatan angin aman (< 10 km/jam untuk menghindari *drift*)
    * Peluang hujan rendah (< 30% dalam rentang 4–6 jam ke depan agar obat tidak tercuci)
    * Suhu & kelembapan ideal untuk penyerapan optimal stomata daun.
  * Menampilkan badge agronomis jelas: `✅ AMAN UNTUK SEMPROT` atau `⚠️ TUNDA PENYEMPROTAN (RISIKO HUJAN/ANGIN KENCANG)`.

---

### 3. 🧠 Memori Percakapan Beruntun (Multi-Turn Conversation History) & Fix Embedding
* **File Terkait:** [agents/diagnosis_agent.py](file:///e:/wa bot longchain/agents/diagnosis_agent.py), [database/repository.py](file:///e:/wa bot longchain/database/repository.py), [api/routes/whatsapp.py](file:///e:/wa bot longchain/api/routes/whatsapp.py), [graph_builder.py](file:///e:/wa bot longchain/graph_builder.py)
* **Penyempurnaan Konteks Dialog:**
  * Menambahkan parameter `conversation_history` ke alur `DiagnosisAgent` dan `TaniState`.
  * Mengambil hingga 5 riwayat percakapan terakhir pengguna dari tabel Supabase `consultation_audits` via method `get_recent_conversation_history`.
  * **Manfaat Nyata:** Petani tidak perlu mengulang keluhan awal. Jika sebelumnya petani mendeskripsikan: *"daun cabai menguning keriting"*, lalu bertanya *"fungisida apa yang cocok?"*, bot memahami konteks bahwa yang dibahas adalah penyakit keriting cabai.
* **Standardisasi Model Embedding:**
  * Menyelaraskan panggilan embedding menggunakan model `gemini-embedding-001` dengan dimensi vektor `output_dimensionality: 768`.
  * Konsisten 100% dengan skema kolom `embedding vector(768)` pada tabel Supabase `knowledge_base` dan fungsi RPC `match_knowledge_base`.

---

### 4. 📱 Antarmuka WhatsApp Interaktif Lengkap (*Interactive UI Dispatcher*)
* **File Terkait:** [services/whatsapp_service.py](file:///e:/wa bot longchain/services/whatsapp_service.py), [api/routes/whatsapp.py](file:///e:/wa bot longchain/api/routes/whatsapp.py), [tests/test_interactive_messages.py](file:///e:/wa bot longchain/tests/test_interactive_messages.py)
* **Komponen yang Dimasukkan:**
  1. **`send_buttons_message`:** Mengirim WhatsApp Reply Buttons hingga 4 tombol (dukungan penuh WAHA engine GOWS) dan 3 tombol untuk Meta Cloud API.
  2. **`send_list_message`:** Mengirim WhatsApp Interactive List dengan sections dan rows untuk pilihan hierarkis (komoditas, daerah pasar).
  3. **`send_poll_message`:** Mengirim jajak pendapat/poll interaktif native WhatsApp.
  4. **Pesan Sambutan Tunggal (*Single Welcome Payload*):** Menggabungkan salam hangat, deskripsi singkat bot, dan 4 tombol tindakan cepat ke dalam satu kiriman tanpa membuat pesan ganda (*no double message*):
     * `[ 🔬 Tanya Penyakit ]`
     * `[ 📷 Konsultasi Foto ]`
     * `[ 💰 Cek Harga Pasar ]`
     * `[ 🌦️ Info Cuaca & Semprot ]`
  5. **Typing Presence Indicator:** Memanggil `/api/startTyping` dan `/api/stopTyping` sebelum dan sesudah komputasi AI/RAG agar bot terasa hidup dan natural layaknya manusia yang sedang mengetik.
  6. **Quoted Reply (`reply_to`):** Setiap jawaban bot secara otomatis mengutip pesan pengguna (`message_id`) yang bersangkutan.
  7. **Graceful Fallback Text Generator:** Jika client WhatsApp pengguna versi lama / web browser tidak mendukung tombol interaktif, payload otomatis dikonversi menjadi daftar teks bernomor yang rapi (`1. Opsi A`, `2. Opsi B`).

---

### 5. ⏱️ Manajemen Sesi 30 Menit & Navigasi Fleksibel (*Session Resilience*)
* **File Terkait:** [services/session_service.py](file:///e:/wa bot longchain/services/session_service.py), [database/repository.py](file:///e:/wa bot longchain/database/repository.py), [tests/test_session_management.py](file:///e:/wa bot longchain/tests/test_session_management.py)
* **Aturan Sesi yang Diterapkan:**
  * **Auto-Reset Timeout 30 Menit:** Jika pengguna tidak membalas selama >30 menit, state sesi otomatis direset kembali ke `main_menu` agar pengguna tidak terjebak pada alur lama.
  * **Shortcut Angka Cepat:** Pengguna dapat mengetik angka tunggal:
    * `1` atau `1.` -> Diagnosa Penyakit Tanaman
    * `2` atau `2.` -> Panduan & Konsultasi Foto
    * `3` atau `3.` -> Pantau Harga Pasar
    * `4` atau `4.` -> Cuaca & Waktu Semprot
  * **Global Escape Hatch:** Kata kunci penolong (`menu`, `batal`, `mulai`, `reset`, `kembali`) dapat diketik kapan saja untuk membatalkan proses dan kembali ke menu utama.
  * **Petunjuk Navigasi (Footer Hint):** Setiap respon panjang otomatis menyematkan petunjuk di bagian bawah:
    `💡 Ketik 'menu' untuk kembali ke pilihan utama.`

---

### 6. 🔒 Patch Keamanan Database & Supabase Linter (100% Resolved)
* **File Terkait:** [database/schema_patch.sql](file:///e:/wa bot longchain/database/schema_patch.sql), [database/repository.py](file:///e:/wa bot longchain/database/repository.py)
* **Penyempurnaan Keamanan Database:**
  * Pembuatan file patch SQL lengkap `database/schema_patch.sql` berisi skema dan kebijakan keamanan.
  * **Aktivasi Row Level Security (RLS) pada 6 Tabel:**
    * `public.user_sessions` (Khusus `service_role`)
    * `public.consultation_audits` (Khusus `service_role`)
    * `public.market_prices` (Read `anon`, Write `service_role`)
    * `public.knowledge_base` (Read `anon`, Write `service_role`)
    * `public.disease_reference_images` (Read `anon`, Write `service_role`)
    * `public.disease_image_gallery` (Read `anon`, Write `service_role`)
  * **Penguncian Fungsi RPC Vector Search:**
    * Menetapkan `SET search_path = public` pada fungsi pencocokan vektor `match_knowledge_base` dan `match_disease_images` untuk mencegah kerentanan SQL search-path injection.
    * Menyetel `SECURITY INVOKER` agar eksekusi fungsi tunduk pada izin pemanggil.
  * **Status Supabase Linter:** 100% Tuntas Bebas Error & Warning.

---

### 7. 📸 Alur Dua Tahap Konsultasi Foto (Computer Vision Pipeline)
* **File Terkait:** [services/cv_preprocessor.py](file:///e:/wa bot longchain/services/cv_preprocessor.py), [agents/diagnosis_agent.py](file:///e:/wa bot longchain/agents/diagnosis_agent.py)
* **Tahap 1 (Edukasi Pengambilan Citra):** Saat menu foto ditekan, bot mengirimkan panduan visual cara memotret:
  * Fokuskan kamera pada daun atau buah yang bergejala
  * Hindari pencahayaan backlight atau bayangan pekat
  * Pastikan gambar tidak buram/goyang.
* **Tahap 2 (Eksekusi Multimodal Real-Time):**
  * Pra-pemrosesan citra dengan filter Laplacian Variance untuk mendeteksi citra buram (*blur check*).
  * Pencarian kemiripan visual terhadap 72 galeri vektor referensi penyakit di Supabase Storage.
  * Penggabungan konteks SOP resmi Balitsa/Kementan melalui RAG.
  * Formulasi rekomendasi 3 pilar: Mekanis/Kultur Teknis, Sanitasi/Hayati, dan Kimiawi/Pestisida Rekomendasi.

---

### 8. 🧪 Ringkasan Verifikasi & Suite Pengujian (Test Suite)

Pengujian dilakukan menggunakan suite pengujian otomatis Python 3.12:

| File Pengujian | Ruang Lingkup Verifikasi | Status |
| :--- | :--- | :---: |
| [tests/test_price_interactive_flow.py](file:///e:/wa bot longchain/tests/test_price_interactive_flow.py) | Alur bertahap pemilihan komoditas -> wilayah pasar -> kartu harga pasar | **PASSED** |
| [tests/test_weather_routing_flow.py](file:///e:/wa bot longchain/tests/test_weather_routing_flow.py) | Routing nama daerah ("bantul"), penanganan typo, rekomendasi waktu aman semprot | **PASSED** |
| [tests/test_interactive_messages.py](file:///e:/wa bot longchain/tests/test_interactive_messages.py) | Reply buttons, lists, polls, typing presence, quoted replies, shortcut 1–4 | **PASSED** |
| [tests/test_session_management.py](file:///e:/wa bot longchain/tests/test_session_management.py) | Timeout inaktif 30 menit, reset keywords (`menu`, `batal`), footer hint | **PASSED** |
| [tests/test_api_endpoints.py](file:///e:/wa bot longchain/tests/test_api_endpoints.py) | Verifikasi HMAC WAHA, handshake token Meta Cloud API, webhook parsing | **PASSED** |
| [tests/test_tani_pintar.py](file:///e:/wa bot longchain/tests/test_tani_pintar.py) | Guardrail anti-halusinasi penyakit, fallback multi-turn, SOP Kementan | **PASSED** |

---

## 📌 Ringkasan Cepat Siap Salin untuk Dosen Pembimbing / Tim

> **Update Rekayasa Sistem TaniPintar — 22 Oktober 2026**
>
> 1. **Alur Interaktif Harga Pasar:** Petani kini dibimbing memilih komoditas (Cabai / Padi) lalu memilih pasar sentra melalui tombol/daftar interaktif untuk mendapatkan perbandingan harga produsen vs konsumen dan tren kenaikan harga.
> 2. **Perbaikan Cuaca & Jam Semprot:** Pertanyaan wilayah (misal: "bantul") langsung menampilkan prakiraan cuaca pertanian mikro beserta indikator agronomis *"Waktu Aman Semprot"* (evaluasi angin & peluang hujan).
> 3. **Memori Multi-Turn:** Bot mengingat hingga 5 percakapan terakhir sehingga petani tidak perlu mengulang keluhan awal saat menanyakan solusi obat lanjutan. Model embedding diselaraskan ke `gemini-embedding-001` (768 dimensi).
> 4. **Polesan WhatsApp Native:** Pesan sambutan dikirim dalam satu pesan tunggal dengan 4 tombol utama, dilengkapi animasi mengetik (*typing indicator*), dan fitur *quoted reply* yang mengutip pesan pengguna.
> 5. **Keamanan Database & Sesi:** Mengaktifkan RLS pada seluruh 6 tabel Supabase (`database/schema_patch.sql`), mengunci fungsi RPC, serta menambahkan auto-timeout sesi 30 menit dan tombol darurat `menu`/`batal`.
> 6. **Testing:** Penambahan test suite baru (`test_price_interactive_flow.py` & `test_weather_routing_flow.py`) untuk memvalidasi stabilitas alur percakapan.
