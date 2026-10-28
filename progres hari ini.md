# 📊 Laporan Rekayasa & Dokumentasi Sistem: TaniPintar Bot
**Proyek:** TaniPintar — AI WhatsApp Assistant Perlindungan Tanaman Cabai & Padi  
**Tanggal Update:** 22 Oktober 2026  
**Status Sesi:** Feature-Complete & Production-Ready  
**Dokumen Terkait:** [dokumentasi hari ini.md](file:///e:/wa%20bot%20longchain/dokumentasi%20hari%20ini.md) • [docs/analisis_progres_hari_ini.md](file:///e:/wa%20bot%20longchain/docs/analisis_progres_hari_ini.md)  
**Stack Teknologi:** FastAPI (Python 3.12) • LangGraph • WAHA (WhatsApp HTTP API - GOWS Engine) • Supabase (PostgreSQL & pgvector) • Google Gemini Multimodal Vision & Embeddings • OpenCV (Laplacian Variance) • BMKG API & WeatherAPI  

---

## 🎯 1. Goal Sistem & Sasaran Pembaruan Hari Ini

### A. Goal Utama Sistem TaniPintar
TaniPintar dibangun untuk mendemokratisasi akses konsultasi agronomis bagi petani cabai (*Capsicum annuum*) dan padi (*Oryza sativa*) langsung dari aplikasi WhatsApp, tanpa mewajibkan petani mengunduh aplikasi tambahan atau membeli perangkat baru. Sistem memadukan:
1. **Skrining Hama & Penyakit Real-Time:** Diagnosa berbasis Dual-RAG (teks keluhan & visual foto tanaman) berstandar SOP Kementan dan Balitsa.
2. **Transparansi Harga Pasar:** Informasi acuan harga produsen (*farmgate*) dan harga konsumen di pasar-pasar sentra pertanian DIY dan sekitarnya.
3. **Prakiraan Cuaca Mikro & Jam Semprot:** Informasi cuaca BMKG tingkat kecamatan/desa untuk menentukan waktu aman penyemprotan pestisida agar tidak luntur tercuci air hujan atau terhempas angin.

### B. Sasaran Teknis Sprint Hari Ini (22 Oktober 2026 / Commit `fad54a7`)
1. **Mengeliminasi Typo Petani:** Mengganti alur teks manual panjang menjadi antarmuka native WhatsApp interaktif (Reply Buttons dan Interactive Lists).
2. **State Machine Terpandu (Guided Flow):** Membangun navigasi bertahap untuk pemilihan komoditas dan daerah sentra pasar.
3. **Konteks Dialog Berkelanjutan:** Menyematkan memori riwayat percakapan (*multi-turn history*) agar petani tidak perlu mengulang keluhan awal saat menanyakan rekomendasi solusi.
4. **Hardening Database Supabase:** Mengaktifkan Row Level Security (RLS) pada seluruh 6 tabel inti dan mengunci `search_path = public` pada fungsi pencarian vektor RPC.
5. **Kerapian Antarmuka (No Double Message):** Mengonsolidasikan pesan selamat datang menjadi satu kiriman tunggal terintegrasi tombol interaktif (*single onboarding payload*) dengan indikator mengetik (*typing presence*).

---

## ⛔ 2. Batasan Sistem (Boundaries & Constraints)

Sistem dirancang dengan batasan operasional dan agronomis yang tegas untuk menjaga akurasi diagnosa dan mencegah kesalahan rekomendasi di lapangan:

### A. Batasan Komoditas & Lingkup Tanaman
* **Eksklusif 2 Komoditas:** Sistem hanya melayani tanaman **Cabai** dan **Padi**.
* **Safe Fallback Guardrail:** Apabila pengguna mengirimkan foto atau pertanyaan di luar dua komoditas target (misalnya kelapa sawit, jagung, tebu, atau foto objek non-tanaman), bot menolak berspekulasi dan memberikan respon terstandar untuk berkonsultasi ke Petugas Penyuluh Lapangan (PPL).

### B. Batasan Pengetahuan Patogen (11 Penyakit Utama)
Basis pengetahuan terverifikasi saat ini mencakup 11 penyakit dan hama prioritas:
* **Cabai (6 Penyakit):** (1) Antraknosa / Patek (*Colletotrichum capsici*), (2) Virus Kuning Gemini / Bulai, (3) Layu Bakteri (*Ralstonia solanacearum*), (4) Layu Fusarium (*Fusarium oxysporum*), (5) Hama Thrips / Keriting Daun, (6) Bercak Daun Cercospora.
* **Padi (5 Penyakit):** (1) Blas Daun & Blas Leher (*Pyricularia oryzae*), (2) Hawar Daun Bakteri / Kresek (*Xanthomonas oryzae*), (3) Penggerek Batang / Sundep & Beluk (*Scirpophaga incertulas*), (4) Penyakit Tungro, (5) Wereng Batang Coklat / WBC (*Nilaparvata lugens*).

### C. Batasan Analisis Citra (Computer Vision)
* **Pengecekan Buram (Blur Detection):** Citra yang dikirim petani diperiksa dengan filter Laplacian Variance OpenCV. Jika citra buram atau bergoyang, sistem meminta pengambilan foto ulang dengan petunjuk fokus dan pencahayaan.
* **Ambang Batas Keyakinan (Confidence Threshold):** Diagnosa AI mensyaratkan skor keyakinan minimal **$\ge 0.70$ (70%)**. Jika di bawah ambang batas, sistem otomatis mengaktifkan *fallback* rujukan ke PPL setempat.

### D. Batasan Sesi & Memori Percakapan
* **Auto-Reset Inaktivitas 30 Menit:** Sesi pengguna yang tidak aktif selama lebih dari 30 menit otomatis direset ke status `main_menu` agar pengguna tidak terjebak pada alur lama.
* **Limitasi Konteks Percakapan:** Bot mengambil maksimal **5 interaksi terakhir** (`LIMIT 5`) dari database untuk menjaga relevansi konteks agronomis dan mencegah pembengkakan token LLM.

### E. Batasan Antarmuka WhatsApp
* **Kapasitas Tombol:** Maksimal **4 tombol interaktif** pada engine WAHA GOWS / **3 tombol** pada Meta Cloud API.
* **Degradasi Elegan (Graceful Degradation):** Jika perangkat WhatsApp pengguna tidak mendukung tombol atau list interaktif, sistem secara otomatis mengonversi menu menjadi pesan teks bernomor (`1. Opsi A`, `2. Opsi B`).

### F. Batasan Geografis Data Pasar
* Data pasar sentra saat ini mencakup wilayah Daerah Istimewa Yogyakarta dan sekitarnya (Sleman, Bantul, Kulon Progo, Kota Yogyakarta, dan Magelang).

---

## 🚀 3. Komponen yang Ditambahkan Hari Ini

Berikut adalah seluruh fitur, komponen logika, antarmuka, dan modul pengujian baru yang diintegrasikan ke dalam repositori:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   KOMPONEN BARU SPRINT 22 OKTOBER 2026                 │
└────────────────────────────────────────────────────────────────────────┘
                                   │
      ┌────────────────────────────┼────────────────────────────┐
      ▼                            ▼                            ▼
[ Alur Interaktif Dua Tahap ] [ Polesan WhatsApp Native ]   [ Penguatan Database ]
 • Step 1: Pilih Komoditas     • Reply Buttons (4 tombol)   • RLS Aktif di 6 Tabel
 • Step 2: Pilih Pasar Sentra  • WhatsApp Interactive Lists • search_path = public
 • Waktu Aman Semprot Cuaca    • Typing Presence Indicator  • Gemini Embed 768-dim
 • Shortcut Angka Cepat 1–4    • Quoted Reply (reply_to)    • 2 File Test Suite Baru
```

### 1. Alur Dua Tahap Pemantauan Harga Pasar (*Interactive Market Price Flow*)
* **File Terkait:** [graph_builder.py](file:///e:/wa%20bot%20longchain/graph_builder.py), [services/price_service.py](file:///e:/wa%20bot%20longchain/services/price_service.py), [database/repository.py](file:///e:/wa%20bot%20longchain/database/repository.py)
* **Mekanisme Baru:**
  * **Tahap 1 (`awaiting_price_commodity`):** Menampilkan tombol pilihan komoditas: `[ 🌶️ Cabai (Rawit/Merah) ]` atau `[ 🌾 Padi & Beras ]`.
  * **Tahap 2 (`awaiting_price_region`):** Menyajikan daftar pasar sentra (Sleman, Bantul, Kulon Progo, Yogyakarta, Magelang).
  * **Tahap 3 (Kartu Ringkasan):** Menampilkan harga tingkat petani (*farmgate*), harga konsumen, tren harga, dan sumber resmi (Bapanas, Disperindag, Pasar Lelang).
  * **Direct Bypass:** Pengguna yang mengetik langsung (contoh: *"harga cabai di bantul"*) tetap langsung diproses ke kartu harga tanpa harus melewati menu bertahap.

### 2. Fitur Cuaca Mikro & Indikator Agronomis "Waktu Aman Semprot"
* **File Terkait:** [graph_builder.py](file:///e:/wa%20bot%20longchain/graph_builder.py), [services/weather_service.py](file:///e:/wa%20bot%20longchain/services/weather_service.py)
* **Mekanisme Baru:**
  * Routing langsung saat petani menyebut nama daerah (contoh: *"bantul"*, *"sleman"*, *"kulon progo"*) ke cuaca BMKG tanpa mental ke pesan pembuka.
  * Evaluasi otomatis kelayakan aplikasi penyemprotan:
    * Kecepatan angin aman (< 10 km/jam agar pestisida tidak melayang/*drift*).
    * Peluang hujan rendah (< 30% dalam 4–6 jam ke depan agar obat tidak tercuci).
    * Pemberian badge status: `✅ AMAN UNTUK SEMPROT` atau `⚠️ TUNDA PENYEMPROTAN`.

### 3. Memori Percakapan Multi-Turn (*Recent Conversation History*)
* **File Terkait:** [agents/diagnosis_agent.py](file:///e:/wa%20bot%20longchain/agents/diagnosis_agent.py), [database/repository.py](file:///e:/wa%20bot%20longchain/database/repository.py)
* **Mekanisme Baru:**
  * Fungsi `get_recent_conversation_history` mengambil 5 riwayat percakapan terakhir dari Supabase table `consultation_audits`.
  * Bot dapat menghubungkan keluhan awal dengan pertanyaan lanjutan (misal: setelah diagnosa bercak daun, petani bertanya *"obatnya apa?"*, bot mengerti tanpa perlu pengulangan jenis tanaman/penyakit).

### 4. Dispatcher WhatsApp Native Lengkap
* **File Terkait:** [services/whatsapp_service.py](file:///e:/wa%20bot%20longchain/services/whatsapp_service.py), [api/routes/whatsapp.py](file:///e:/wa%20bot%20longchain/api/routes/whatsapp.py)
* **Mekanisme Baru:**
  * `send_buttons_message`: Mengirim reply buttons interaktif WhatsApp.
  * `send_list_message`: Mengirim pilihan bertingkat berbasis sections & rows.
  * `send_poll_message`: Mengirim polling interaktif.
  * `startTyping` & `stopTyping`: Menyalakan indikator mengetik saat AI melakukan inferensi.
  * `reply_to`: Respon bot otomatis mengutip pesan pengguna.
  * *Single Onboarding Payload*: Salam pembuka dan 4 tombol menu dikirim dalam satu payload utuh tanpa memicu pesan ganda.

### 5. Patch Keamanan Database Supabase (`database/schema_patch.sql`)
* **File Terkait:** [database/schema_patch.sql](file:///e:/wa%20bot%20longchain/database/schema_patch.sql)
* **Mekanisme Baru:**
  * Pengaktifan RLS pada 6 tabel: `user_sessions`, `consultation_audits`, `market_prices`, `knowledge_base`, `disease_reference_images`, dan `disease_image_gallery`.
  * Penguncian fungsi RPC `match_knowledge_base` dan `match_disease_images` dengan parameter `SET search_path = public` dan `SECURITY INVOKER`.

### 6. Modul Pengujian Otomatis Baru
* **File Terkait:** [tests/test_price_interactive_flow.py](file:///e:/wa%20bot%20longchain/tests/test_price_interactive_flow.py), [tests/test_weather_routing_flow.py](file:///e:/wa%20bot%20longchain/tests/test_weather_routing_flow.py)
* Menambahkan validasi lengkap untuk transisi state harga pasar dan routing cerdas cuaca wilayah.

---

## 📈 4. Metrik Kunci Sistem (Engineering & Agronomic Metrics)

Seluruh indikator kuantitatif performa dan kriteria operasional sistem dirangkum dalam tabel metrik berikut:

| Kategori Metrik | Indikator Spesifik | Nilai / Ambang Batas | Status & Validasi Teknis |
| :--- | :--- | :--- | :--- |
| **Model AI & Vektor** | Dimensi Vektor Embedding | **768 Dimensi** | Menggunakan model `gemini-embedding-001` selaras dengan tipe data `vector(768)` di pgvector Supabase |
| **Guardrail Diagnosa** | Ambang Batas Keyakinan AI | **$\ge 0.70$ (70%)** | Keyakinan $< 0.70$ otomatis dialihkan ke SOP rujukan Petugas Penyuluh Lapangan (PPL) |
| **Dataset Visual** | Galeri Referensi Penyakit | **72 Vektor RAG / 292 Foto** | Tersimpan di Supabase Storage bucket `disease-references` dengan visual similarity search |
| **Manajemen Sesi** | Batas Waktu Inaktif (Timeout) | **30 Menit** | Reset otomatis ke state `main_menu` pada tabel `user_sessions` saat pengguna inaktif > 30 menit |
| **Memori Percakapan** | Kapasitas Riwayat Multi-Turn | **5 Percakapan Terakhir** | Query `get_recent_conversation_history` dibatasi `LIMIT 5` untuk efisiensi token prompt |
| **Agronomi Semprot** | Kecepatan Angin Maksimal | **< 10 km/jam** | Mencegah melayang (*drift*) bahan aktif pestisida ke luar area sasaran |
| **Agronomi Semprot** | Peluang Hujan Maksimal | **< 30% (Jendela 4–6 Jam)** | Menghindari pencucian (*wash-off*) pestisida oleh air hujan sebelum terserap stomata |
| **Antarmuka WA** | Batas Tombol Cepat | **4 Tombol** (WAHA) / **3** (Meta) | Single welcome payload terkirim tanpa terjadi pesan ganda (*no double message*) |
| **Respon Webhook** | Latensi Respon HTTP Inbound | **< 200 ms** | Pemrosesan pesan dialihkan ke FastAPI `BackgroundTasks` non-blocking |
| **Keamanan Data** | Supabase Database Linter | **0 Error, 0 Warning (100%)** | 6 tabel berstatus RLS Aktif, fungsi RPC dilindungi `search_path = public` |
| **Kualitas Kode** | Uji Coba Unit & Integrasi | **100% Passed (37+ Test Cases)** | Terverifikasi lewat `test_interactive_messages`, `test_session_management`, `test_price_interactive_flow`, dll. |

---

## 🔄 5. Komponen yang Diubah (What Was Changed)

Berikut adalah ringkasan perubahan teknis pada 15 file utama di repositori:

| File yang Diubah | Komponen yang Dimodifikasi | Dampak Perubahan |
| :--- | :--- | :--- |
| [graph_builder.py](file:///e:/wa%20bot%20longchain/graph_builder.py) | • Penambahan state `awaiting_price_commodity` & `awaiting_price_region`<br/>• Node `price_prompt_node` & `price_region_prompt_node`<br/>• Routing cerdas nama daerah cuaca (Bantul, Sleman, Kulon Progo)<br/>• Integrasi `FOOTER_MENU_HINT` pada balasan bertahap | Alur harga pasar menjadi interaktif dua tahap; input nama wilayah langsung membuka cuaca agronomis |
| [services/whatsapp_service.py](file:///e:/wa%20bot%20longchain/services/whatsapp_service.py) | • Implementasi `send_buttons_message` (hingga 4 opsi)<br/>• Implementasi `send_list_message` & `send_poll_message`<br/>• Indikator *typing presence* (`startTyping`/`stopTyping`)<br/>• Quoted reply payload (`reply_to`)<br/>• Generator fallback teks bernomor | Antarmuka pesan WhatsApp tampil modern, interaktif, dan memiliki penanganan cadangan jika tombol tidak didukung |
| [api/routes/whatsapp.py](file:///e:/wa%20bot%20longchain/api/routes/whatsapp.py) | • Penyederhanaan pesan sambutan menjadi *single welcome payload*<br/>• Parser payload tombol interaktif WAHA (`selected_button_id`, `title`)<br/>• Pemanggilan typing indicator otomatis sebelum pemrosesan LangGraph | Menghilangkan masalah pesan dobel; webhook responsif dan interaktif terhadap klik tombol |
| [services/price_service.py](file:///e:/wa%20bot%20longchain/services/price_service.py) | • Pemisahan logika pencarian komoditas vs pasar sentra<br/>• Format kartu perbandingan harga produsen (*farmgate*) vs konsumen<br/>• Integrasi data pasar sentra DIY & Magelang | Data harga tersaji lebih terperinci dengan tren kenaikan/penurunan harga |
| [database/repository.py](file:///e:/wa%20bot%20longchain/database/repository.py) | • Fungsi `get_recent_conversation_history`<br/>• Penyempurnaan query lookup harga komoditas wilayah<br/>• Penyelarasan kolom sesi | Memungkinkan bot membaca histori interaksi sebelumnya dari database Supabase |
| [database/schema_patch.sql](file:///e:/wa%20bot%20longchain/database/schema_patch.sql) | • DDL aktivasi RLS pada 6 tabel utama<br/>• Penguncian `search_path = public` pada fungsi pencocokan vektor RPC | Menyelesaikan seluruh temuan Supabase Security Linter |
| [agents/diagnosis_agent.py](file:///e:/wa%20bot%20longchain/agents/diagnosis_agent.py) | • Integrasi `conversation_history` pada prompt diagnosa<br/>• Standarisasi pemanggilan embedding ke model `gemini-embedding-001` (768 dimensi) | Bot memahami konteks diagnosa sebelumnya dan dimensi vektor presisi dengan database |
| [services/weather_service.py](file:///e:/wa%20bot%20longchain/services/weather_service.py) | • Integrasi logika evaluasi cuaca mikro BMKG Adm4<br/>• Logika penentuan status *Waktu Aman Semprot* | Petani memperoleh saran agronomis waktu terbaik aplikasi pestisida |
| [services/session_service.py](file:///e:/wa%20bot%20longchain/services/session_service.py) | • Logika evaluasi timeout 30 menit<br/>• Penanganan kata kunci reset global (`menu`, `batal`, `mulai`, `reset`) | Sesi pengguna lebih tangguh dan mudah dinavigasi |
| [services/cv_preprocessor.py](file:///e:/wa%20bot%20longchain/services/cv_preprocessor.py) | • Filter Laplacian Variance untuk deteksi blur citra | Memvalidasi kualitas foto sebelum diproses oleh model vision |
| [tests/test_interactive_messages.py](file:///e:/wa%20bot%20longchain/tests/test_interactive_messages.py) | • 16 skenario pengujian tombol, list, polling, quoted reply, dan single payload | Memastikan pengiriman pesan interaktif berfungsi 100% |
| [tests/test_session_management.py](file:///e:/wa%20bot%20longchain/tests/test_session_management.py) | • 5 skenario verifikasi timeout 30 menit, reset keywords, dan footer hint | Menjamin ketahanan sesi percakapan |
| [tests/test_price_interactive_flow.py](file:///e:/wa%20bot%20longchain/tests/test_price_interactive_flow.py) | • Verifikasi pemilihan bertahap komoditas -> wilayah -> kartu harga | Menjamin alur harga terpandu berjalan tanpa kegagalan |
| [tests/test_weather_routing_flow.py](file:///e:/wa%20bot%20longchain/tests/test_weather_routing_flow.py) | • Verifikasi routing nama daerah cuaca dan fitur jam aman semprot | Menjamin penanganan nama lokasi tepat sasaran |

---

## 📌 6. Ringkasan Eksekutif untuk Bimbingan Dosen / Tim (Siap Salin)

> **Ringkasan Kemajuan Rekayasa Sistem TaniPintar — 22 Oktober 2026**
>
> 1. **Antarmuka WhatsApp Interaktif Native:** Menu bot kini bertransformasi menggunakan WhatsApp Reply Buttons (4 tombol menu utama) dan Interactive Lists. Pesan sambutan dikirim dalam satu pesan tunggal terpadu lengkap dengan indikator animasi mengetik (*typing presence*) dan *quoted reply* yang mengutip pesan pengguna.
> 2. **Alur Terpandu Dua Tahap Cek Harga Pasar:** Mengatasi kendala salah ketik (*typo*) petani dengan memandu pemilihan komoditas (Cabai vs Padi/Beras) lalu pemilihan pasar sentra (Sleman, Bantul, Kulon Progo, Yogyakarta, Magelang) untuk menyajikan harga produsen vs konsumen dan tren harga terkini.
> 3. **Penyempurnaan Cuaca & Jam Aman Semprot:** Pengetikan nama wilayah pertanian (contoh: *"bantul"*) langsung terhubung ke prakiraan cuaca mikro BMKG disertai evaluasi agronomis *"Waktu Aman Semprot"* (analisis kecepatan angin < 10 km/jam dan peluang hujan < 30%).
> 4. **Memori Percakapan Multi-Turn & Embedding 768-Dim:** Bot mengingat hingga 5 percakapan terakhir dari database Supabase sehingga petani dapat langsung menanyakan solusi penanganan tanpa mengulang keluhan awal. Model embedding distandardisasi ke `gemini-embedding-001` (768 dimensi).
> 5. **Pengerasan Keamanan Database & Sesi:** Mengaktifkan Row Level Security (RLS) pada 6 tabel database (`database/schema_patch.sql`), mengunci fungsi pencarian vektor RPC, serta menyematkan timeout inaktif 30 menit dan tombol penyelamat navigasi (`menu`/`batal`).
> 6. **Jaminan Kualitas:** Seluruh modul pengujian otomatis (37+ skenario uji pada 6 test suite) berhasil lulus 100% (**Green**).
