# 🌾 TaniPintar Bot: WhatsApp AI Support Agent with RAG & Memory

> Asisten Pertanian Cerdas Berbasis WhatsApp untuk Skrining Hama/Penyakit Tanaman (Khusus Cabai & Padi), Transparansi Harga Komoditas Pangan, Pengarsipan Bukti Foto, Prediksi Cuaca Pertanian, dan Rekomendasi Nutrisi/Pestisida Spesifik.

---

## 🚀 6 Fitur Utama MVP

1. **🔬 Konsultasi Teks (Knowledge Base 11 Penyakit)**:
   - **Cabai (6 Penyakit):** (1) Antraknosa / Patek, (2) Virus Kuning Gemini / Bulai, (3) Layu Bakteri, (4) Layu Fusarium, (5) Hama Thrips / Keriting Daun, (6) Bercak Daun Cercospora.
   - **Padi (5 Penyakit):** (1) Blas Daun & Blas Leher, (2) Hawar Daun Bakteri (Kresek / HDB), (3) Penggerek Batang (Sundep & Beluk), (4) Penyakit Tungro, (5) Wereng Batang Coklat (WBC).
   - *Structured Output:* Nama penyakit, patogen, dan 3 Pilar Penanganan Praktis (Mekanis, Sanitasi, dan Bahan Aktif Kimiawi terdaftar).
2. **📸 Konsultasi Foto (Multimodal Vision Khusus Cabai & Padi)**:
   - Petani mengirimkan foto daun/batang/buah yang sakit ke WhatsApp.
   - Bot memvalidasi apakah foto adalah tanaman Cabai atau Padi. Jika bukan (misal sawit, jagung, apel, atau foto selain tanaman), bot menolak berspekulasi secara aman.
   - Foto dianalisis secara visual dengan Gemini 1.5 Flash Vision dan diarsipkan otomatis ke **Supabase Storage** (`crop-symptoms`).
3. **📊 Harga Pasar Padi & Cabai Seluruh Indonesia (Otomatis & Admin)**:
   - **Otomatis:** Pembaruan harian otomatis berbasis acuan pasar nasional (Cabai Rawit Merah, Cabai Merah Keriting, Gabah Kering Panen, Beras Medium) per wilayah sentra pertanian.
   - **Admin Override:** Admin dapat menginput atau memperbarui harga harian kapan saja via REST API: `POST /api/v1/admin/prices` atau langsung di Supabase Table Editor.
4. **📋 Riwayat Konsultasi Petani**:
   - Petani cukup mengetik *"riwayat"* di WhatsApp untuk melihat rekam jejak konsultasi dan diagnosis terakhirnya beserta status penanganan PPL.
5. **🌦️ Prediksi Cuaca Pertanian**:
   - Terintegrasi dengan Open-Meteo API untuk seluruh kota/kabupaten di Indonesia tanpa kuota API key.
   - Menyajikan prakiraan cuaca, suhu, kelembapan, serta *Advisory Penyemprotan & Pemupukan* (menentukan jam aman aplikasi pestisida agar tidak luntur tercuci hujan).
6. **🧪 Rekomendasi Pestisida & Pupuk Spesifik**:
   - Perhitungan formulasi dosis pupuk (Urea, NPK, SP-36, KCl, KNO3 Putih, MKP, Kalsium, Silika) sesuai fase tanaman (Vegetatif vs Generatif) dan pestisida pendamping berimbang.

---

## 🏗️ Tech Stack

- **PydanticAI & Google Gemini**: Structured Output, Multimodal Vision, Guardrail Ambang Batas ($\ge 0.70$), dan Text Embeddings.
- **LangGraph**: StateGraph percakapan dengan routing conditional untuk 6 layanan.
- **Supabase**:
  - `pgvector`: Pencarian semantik RAG 11 penyakit.
  - `PostgreSQL`: Tabel `consultation_audits`, `chat_sessions`, dan `market_prices`.
  - `Supabase Storage`: Pengarsipan foto gejala fisik tanaman.
- **FastAPI**: Backend asynchronous webhook handler untuk WhatsApp Cloud API resmi dengan `BackgroundTasks`.

---

## 📁 Struktur Folder Proyek

```text
tanipintar-bot/
├── agents/                      # PydanticAI Agents & Tools
│   ├── diagnosis_agent.py      # Diagnosa RAG 11 Penyakit & Multimodal Vision
│   ├── fertilizer_agent.py     # Rekomendasi pupuk & pestisida spesifik
│   ├── market_agent.py         # Agen acuan harga pasar
│   ├── schemas.py              # Pydantic Schemas untuk 6 fitur MVP
│   └── prompts.py              # Prompt agronomi & Safe Fallback Guardrail
│
├── api/                         # FastAPI Web Layer
│   ├── app.py                  # Factory instance FastAPI & CORS
│   └── routes/
│       ├── whatsapp.py         # Webhook receiver Meta Graph API
│       ├── admin.py            # Portal API Admin input harga pasar
│       └── health.py           # Health check endpoint
│
├── core/                        # Konfigurasi & Logger
│   ├── config.py               # Pydantic Settings & ENV loader
│   └── logger.py               # Structured logging (UTF-8 safe)
│
├── data/                        # Knowledge Base & Dataset
│   ├── knowledge/
│   │   ├── cabai_diseases.json # 6 Penyakit Cabai
│   │   └── padi_diseases.json  # 5 Penyakit Padi
│   └── ingest_knowledge.py     # Script indexing dokumen ke Supabase pgvector
│
├── database/                    # Supabase Client & Vector Store
│   ├── supabase_client.py      # Supabase client singleton
│   ├── repository.py           # Operasi database (RAG RPC, riwayat, harga pasar)
│   └── schema.sql              # DDL Script: pgvector, market_prices, consultation_audits
│
├── services/                    # Integrasi Eksternal
│   ├── whatsapp_service.py     # Pengirim pesan & pengunduh media Meta WhatsApp API
│   ├── storage_service.py      # Pengunggah foto ke Supabase Storage (crop-symptoms)
│   ├── price_service.py        # Harga pasar otomatis harian & lookup database
│   └── weather_service.py      # Integrasi cuaca Open-Meteo & spray advisory
│
├── tests/                       # Automated Test Suites
│   ├── test_tani_pintar.py     # Uji komprehensif 6 fitur MVP & guardrail
│   └── test_api_endpoints.py   # Uji integrasi endpoint webhook, admin, & health
│
├── graph_builder.py             # LangGraph StateGraph untuk 6 Fitur MVP
├── main.py                      # Server Uvicorn Entrypoint
├── pyproject.toml               # Konfigurasi dependensi
├── requirements.txt             # Daftar dependensi pip/uv
├── .env.example                 # Template variabel lingkungan
└── README.md                    # Dokumentasi ini
```

---

## 🚀 Panduan Menjalankan Sistem

### 1. Inisialisasi Environment
```bash
# Buat venv & instal dependensi
uv venv
uv pip install -r requirements.txt
```

### 2. Setup Supabase
1. Buka SQL Editor di Dashboard Supabase Anda, salin seluruh isi [database/schema.sql](file:///e:/wa%20bot%20longchain/database/schema.sql) dan jalankan.
2. Buka menu **Storage**, buat bucket baru bernama `crop-symptoms` dengan akses **Public**.

### 3. Konfigurasi .env
Salin `.env.example` menjadi `.env` dan masukkan kredensial:
```env
GEMINI_API_KEY=AIzaSy...
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJh...
META_WA_PHONE_NUMBER_ID=1234567890
META_WA_ACCESS_TOKEN=EAA...
META_WA_VERIFY_TOKEN=tanipintar_webhook_verify_token_secret
ADMIN_API_KEY=tanipintar_admin_secret_2026
```

### 4. Index Knowledge Base ke pgvector
```bash
.venv\Scripts\python data/ingest_knowledge.py
```

### 5. Jalankan Pengujian Otomatis
```bash
.venv\Scripts\python -m unittest discover tests
```

### 6. Jalankan Server
```bash
.venv\Scripts\python main.py
```
Akses Swagger UI di: `http://localhost:8000/docs`
- **Portal Admin & PPL** (Header: `X-Admin-Key: tanipintar_admin_secret_2026`):
  - Harga Pasar: `POST /api/v1/admin/prices` (Create), `GET /api/v1/admin/prices` (Read), `PUT /api/v1/admin/prices/{id}` (Update), `DELETE /api/v1/admin/prices/{id}` (Delete)
  - Audit & Rujukan PPL: `GET /api/v1/admin/consultations` (Read/Filter), `PATCH /api/v1/admin/consultations/{id}` (Follow-up), `DELETE /api/v1/admin/consultations/{id}` (Delete)
- **WhatsApp Webhook**:
  - `GET /webhook` (Verifikasi Handshake Token Meta)
  - `POST /webhook` (Penerima Pesan & Foto Realtime)

