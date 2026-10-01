# 📑 LAPORAN LENGKAP SISTEM & ARSITEKTUR: TANIPINTAR BOT
**WhatsApp AI Agricultural Support Agent with RAG, Multimodal Vision, and Memory**

---

## 📌 1. Ringkasan Eksekutif Proyek

**TaniPintar Bot** adalah sistem asisten virtual berbasis kecerdasan buatan (*Artificial Intelligence*) yang beroperasi melalui platform **WhatsApp** (didukung oleh WAHA WebJS dan Meta WhatsApp Cloud API). Sistem ini dirancang untuk mendemokratisasi akses konsultasi agronomi bagi petani Indonesia, dengan fokus utama pada dua komoditas pangan paling strategis: **Padi (*Oryza sativa*)** dan **Cabai (*Capsicum annuum*)**.

Sistem menggabungkan pendekatan **Retrieval-Augmented Generation (RAG)** semantik dengan basis data vektor (*pgvector*), analisis citra visual multimodal (**Google Gemini 3.5 Flash Vision**), mesin alur percakapan (**LangGraph StateGraph**), prakiraan cuaca pertanian real-time (**WeatherAPI.com & Open-Meteo**), transparansi harga pasar komoditas, serta portal administrasi untuk Petugas Penyuluh Lapangan (PPL).

### Status Implementasi Saat Ini
- **Status Sistem**: *Fully Functional MVP / Production-Ready Core*.
- **Cakupan Pengetahuan**: 11 Penyakit & Hama Utama (6 Cabai, 5 Padi) terindeks 768 dimensi di Supabase pgvector.
- **Koleksi Dataset Visual**: 292 foto referensi terverifikasi yang tersimpan di Supabase Storage (`disease-references`) dan terhubung otomatis pada hasil diagnosa bot.
- **Konektivitas WhatsApp**: Berjalan secara live menggunakan WAHA engine `WEBJS` terhubung ke nomor bot WhatsApp aktif (`62895418133345`).
- **Kualitas Kode & Pengujian**: 13/13 automated test suites lolos (100% pass).

---

## 🏗️ 2. Arsitektur Sistem (System Architecture)

Arsitektur TaniPintar dibangun mengacu pada prinsip *Separation of Concerns* (Pemisahan Tanggung Jawab) antara lapisan presentasi (*WhatsApp Gateway*), orkestrasi alur (*LangGraph State Machine*), logika bisnis agronomi (*PydanticAI Agents*), basis data vektor & relasional (*Supabase PostgreSQL*), serta integrasi pihak ketiga (*WeatherAPI, Gemini API*).

### 2.1 Diagram Arsitektur Tingkat Tinggi (High-Level Architecture)

```mermaid
flowchart TB
    subgraph Pengguna["🌾 Lapisan Petani (End User)"]
        Petani["Petani via WhatsApp\n(Teks, Foto Daun/Buah, Pertanyaan)"]
    end

    subgraph WA_Gateway["📱 WhatsApp Gateway Layer"]
        WAHA["WAHA (WhatsApp HTTP API)\nEngine: WEBJS / Puppeteer"]
        MetaAPI["Meta WhatsApp Cloud API\n(Official Enterprise Option)"]
    end

    subgraph Backend["⚙️ Backend Server (FastAPI Core)"]
        Webhook["FastAPI Webhook Handler\n/webhook (Async BackgroundTasks)"]
        RouterNode["Router Node (Intent Classifier)\nLangGraph StateGraph"]
        
        subgraph SubAgents["🤖 Agentic Service Layer"]
            DiagAgent["Diagnosis Agent\n(RAG & Gemini Vision)"]
            FertAgent["Fertilizer Agent\n(Formulasi Vegetatif/Generatif)"]
            MarketAgent["Market Price Service\n(Kalkulasi Harian & DB Lookup)"]
            WeatherSvc["Weather Service\n(WeatherAPI.com + Open-Meteo)"]
            HistSvc["History Service\n(Audit Riwayat Petani)"]
        end

        Guardrail["Guardrail & Formatter Node\n(Threshold >= 0.70 & Anti-Halusinasi)"]
        AuditSaver["Audit Saver Node\n(Auto-log Consultation)"]
        AdminAPI["Portal Admin REST API\n/api/v1/admin (CRUD Harga & PPL)"]
    end

    subgraph SupabaseDB["🗄️ Supabase Cloud (Database & Storage)"]
        VectorDB[("knowledge_base\n(pgvector 768-dim, IVFFlat)")]
        RefImages[("disease_reference_images\n(292 Foto Dataset Lapangan)")]
        Audits[("consultation_audits\n(Rekam Jejak Konsultasi Petani)")]
        Sessions[("chat_sessions\n(State Memory Persistence)")]
        Prices[("market_prices\n(Data Harga Acuan Harian)")]
        StorageBucket[("Supabase Storage\n'crop-symptoms' & 'disease-references'")]
    end

    subgraph External["🌐 External AI & APIs"]
        GeminiFlash["Google Gemini 3.5 Flash\n(Multimodal Vision & Reasoning)"]
        GeminiEmbed["Google Gemini-Embedding-001\n(768-dim Text Vectorizer)"]
        WeatherAPI["WeatherAPI.com\n(Realtime Weather + Advisory)"]
    end

    %% Flows
    Petani <-->|Kirim/Terima Pesan & Foto| WAHA
    Petani -.->|Alternatif Cloud API| MetaAPI
    WAHA -->|Webhook POST < 200ms| Webhook
    MetaAPI -->|Webhook POST| Webhook
    Webhook --> RouterNode
    
    RouterNode -->|Foto| DiagAgent
    RouterNode -->|Teks Gejala| DiagAgent
    RouterNode -->|Tanya Pupuk| FertAgent
    RouterNode -->|Tanya Harga| MarketAgent
    RouterNode -->|Tanya Cuaca| WeatherSvc
    RouterNode -->|Ketik 'Riwayat'| HistSvc

    DiagAgent <-->|Cosine Match RPC| VectorDB
    DiagAgent <-->|Vision / Reasoning| GeminiFlash
    DiagAgent <-->|Embed Query| GeminiEmbed
    DiagAgent -->|Upload Foto Gejala| StorageBucket
    DiagAgent <-->|Link Foto Pembanding| RefImages

    WeatherSvc <-->|API Key: 76d7a4136a6948e8ac464008250810| WeatherAPI
    MarketAgent <-->|Query/Upsert Harga| Prices
    HistSvc <-->|Ambil Histori Petani| Audits

    SubAgents --> Guardrail
    Guardrail --> AuditSaver
    AuditSaver --> Audits
    AuditSaver --> Sessions
    AuditSaver -->|Kirim Pesan WhatsApp Balasan| WAHA
    AuditSaver -.->|Kirim Pesan| MetaAPI

    AdminAPI <-->|Full CRUD| Prices
    AdminAPI <-->|Tindak Lanjut Rujukan PPL| Audits
```

---

### 2.2 Diagram Alur StateGraph Percakapan (LangGraph Workflow)

```mermaid
stateDiagram-v2
    [*] --> router: Pesan / Foto Masuk
    
    state router {
        direction LR
        Deteksi_Media --> vision: Terdapat Foto (media_id)
        Deteksi_Teks --> weather: Kata kunci 'cuaca', 'hujan', 'nyemprot'
        Deteksi_Teks --> price: Kata kunci 'harga', 'pasar', 'gabah'
        Deteksi_Teks --> fertilizer: Kata kunci 'pupuk', 'dosis', 'kalsium'
        Deteksi_Teks --> history: Kata kunci 'riwayat', 'rekam jejak'
        Deteksi_Teks --> greeting: Kata kunci 'halo', 'menu', 'bantuan'
        Deteksi_Teks --> diagnosis: Gejala Penyakit (Default)
    }

    vision --> formatter: Hasil Analisis Vision & Link Foto Storage
    diagnosis --> formatter: Hasil Pencarian RAG 11 Penyakit
    weather --> formatter: Suhu, Hujan, Saran Semprot & Pupuk
    price --> formatter: Rekap Harga Petani vs Pasar
    fertilizer --> formatter: Formulasi Dosis & Nutrisi Tanaman
    history --> formatter: Daftar Riwayat Konsultasi Sebelumnya
    greeting --> formatter: Menu 6 Layanan & Petunjuk

    state formatter {
        Cek_Komoditas: Verifikasi apakah Cabai atau Padi?
        Cek_Confidence: Apakah Confidence Score >= 0.70?
        Beri_Rujukan: Jika < 0.70 -> Tampilkan Pesan Aman Rujukan PPL
        Beri_Solusi: Jika >= 0.70 -> Format 3 Pilar (Mekanis, Sanitasi, Kimiawi) + Link Foto Referensi
    }

    formatter --> audit_saver: Simpan Audit ke Supabase
    audit_saver --> [*]: Selesai & Kirim ke WhatsApp
```

---

## 💻 3. Spesifikasi Teknologi (Technology Stack)

Sistem TaniPintar dibangun menggunakan ekosistem teknologi modern berbasis Python asinkron, LLM multimodal mutakhir, dan infrastruktur cloud yang tangguh:

### 3.1 Ringkasan Komponen Tech Stack

| Layer / Kategori | Komponen / Pustaka | Versi | Peran & Fungsi dalam Sistem |
| :--- | :--- | :--- | :--- |
| **Bahasa & Runtime** | **Python** | `3.12` / `3.10+` | Bahasa pemrograman utama untuk backend, AI, dan data pipeline. |
| **Backend & Web Framework** | **FastAPI** | `>=0.115.0` | Framework web REST API asynchronous berkecepatan tinggi untuk webhook WhatsApp dan portal admin. |
| **Web Server (ASGI)** | **Uvicorn [standard]** | `>=0.30.0` | ASGI HTTP server untuk menjalankan FastAPI secara asinkron dengan fitur auto-reload. |
| **Validasi & Konfigurasi** | **Pydantic & Pydantic-Settings** | `>=2.8.0` / `>=2.4.0` | Validasi tipe data ketat, serialisasi skema agronomi, dan pemuatan variabel lingkungan (.env). |
| **Orkestrator Alur (Agentic)** | **LangGraph** | `>=0.2.20` | Mesin StateGraph untuk navigasi intent percakapan, cyclical state management, dan conditional routing. |
| **Framework LLM & Abstraksi** | **PydanticAI & LangChain Core** | `>=0.0.18` / `>=0.3.0` | Framework agen cerdas untuk penegakan Structured Output JSON dan penanganan fallback model. |
| **Model AI Vision & Teks** | **Google Gemini 3.5 Flash** | API 2026 / latest | Model multimodal untuk inspeksi visual foto penyakit tanaman dan penalaran agronomi. |
| **Model Embedding Teks** | **Google Gemini-Embedding-001** | `output_dim: 768` | Vektorisasi semantik dokumen pengetahuan 11 penyakit dan kueri pertanyaan petani. |
| **SDK Google GenAI** | **google-genai & langchain-google-genai** | `>=0.1.1` / `>=2.0.0` | Driver resmi Google untuk integrasi LLM dan Text Embedding API. |
| **Basis Data Relasional & Vektor**| **Supabase Cloud (PostgreSQL 15+)** | Cloud Hosted | Database relasional untuk sesi chat, audit PPL, harga pasar, dan katalog foto dataset. |
| **Pencarian Semantik (Vector)** | **pgvector** (Postgres Extension) | Enabled | Penyimpanan vektor 768 dimensi dan kalkulasi kemiripan kosinus dengan indeks `IVFFlat`. |
| **SDK Supabase** | **supabase (Python Client)** | `>=2.6.0` | Client resmi Python untuk query PostgREST, RPC `match_knowledge`, dan interaksi Storage API. |
| **Penyimpanan Berkas (Storage)** | **Supabase Storage** | Public Buckets | Bucket `crop-symptoms` (foto keluhan petani) dan `disease-references` (292 foto dataset). |
| **Klien HTTP Asinkron** | **HTTPX** | `>=0.27.0` | Klien HTTP non-blocking untuk unduh media foto WhatsApp, query WeatherAPI, dan Open-Meteo. |
| **Gateway WhatsApp (Self-Hosted)** | **WAHA (WhatsApp HTTP API)** | Docker `devlikeapro/waha` | Gateway WhatsApp berbasis browser Chromium headless (WebJS engine) tanpa biaya per pesan. |
| **Gateway WhatsApp (Resmi)** | **Meta WhatsApp Cloud Graph API** | `v20.0` | Alternatif resmi WhatsApp Business Enterprise melalui Webhook Meta Graph API. |
| **Layanan Cuaca Utama** | **WeatherAPI.com** | REST API | Penyedia data cuaca real-time, presipitasi, kelembapan, dan peluang hujan per kota di Indonesia. |
| **Layanan Cuaca Fallback** | **Open-Meteo API** | Free REST API | Fallback otomatis tanpa kuota untuk koordinat dan prakiraan cuaca sentra pertanian Indonesia. |
| **Kontainerisasi & DevOps** | **Docker & Docker Compose** | Docker v24+ | Pembungkus container untuk mengisolasi aplikasi `tanipintar-bot` dan gateway `waha`. |

---

## ⚙️ 4. Kebutuhan Sistem (System Requirements)

Berikut adalah rincian prasyarat teknis perangkat keras (*hardware*), sistem operasi, dependensi paket, dan kunci API eksternal yang dibutuhkan untuk menjalankan sistem TaniPintar:

### 4.1 Kebutuhan Perangkat Keras (Hardware Requirements)

| Komponen Perangkat Keras | Spesifikasi Minimum (Development) | Spesifikasi Rekomendasi (Production VPS) |
| :--- | :--- | :--- |
| **Processor (CPU)** | 2 Core CPU (x86_64 atau ARM64) | 4 vCPU Core (2.4 GHz+) |
| **Memori (RAM)** | 4 GB RAM *(WAHA WebJS membutuhkan minimal 1.5 GB untuk Chromium)* | 8 GB RAM *(Direkomendasikan agar browser headless lancar)* |
| **Penyimpanan (Disk Storage)**| 20 GB SSD kosong | 40 GB SSD NVMe |
| **Koneksi Jaringan (Network)** | Akses internet stabil (Unduh/Unggah $\ge$ 10 Mbps) | Bandwidth 100 Mbps+, IP Publik statis, Latensi rendah ke Supabase |

> [!IMPORTANT]
> **Catatan Alokasi Memori WAHA**: Engine `WEBJS` pada container WAHA menjalankan browser Chromium tanpa kepala (*headless browser*) yang menyimpan sesi WhatsApp Web. Alokasikan setidaknya **2 GB RAM khusus untuk container WAHA** agar tidak terkena *Out of Memory (OOM) Killer*.

---

### 4.2 Kebutuhan Perangkat Lunak & Sistem Operasi (Software & OS Requirements)

1. **Sistem Operasi**:
   - **Linux**: Ubuntu 22.04 LTS / 24.04 LTS atau Debian 12 (Sangat direkomendasikan untuk produksi).
   - **Windows**: Windows 10/11 64-bit dengan WSL2 (Windows Subsystem for Linux) atau PowerShell 7+.
   - **macOS**: macOS Monterey 12+ (Apple Silicon atau Intel).
2. **Container Engine**:
   - **Docker Engine**: Versi `24.0.0` atau yang lebih baru.
   - **Docker Compose**: Versi `v2.20.0` atau yang lebih baru.
3. **Runtime Python (Jika Menjalankan Bare-Metal / Local Virtualenv)**:
   - Python versi `3.10`, `3.11`, atau `3.12` (Direkomendasikan `3.12-slim` seperti pada Dockerfile).
   - Package manager: `uv` (sangat cepat) atau `pip` standar.
4. **Git**: Versi `2.34+` untuk manajemen versi kode sumber.

---

### 4.3 Kebutuhan Pustaka & Dependensi Python (`requirements.txt`)

Seluruh paket Python berikut didefinisikan dalam [`requirements.txt`](file:///e:/wa%20bot%20longchain/requirements.txt) dan [`pyproject.toml`](file:///e:/wa%20bot%20longchain/pyproject.toml):

```text
fastapi>=0.115.0              # Framework Web REST API & Webhook Handler
uvicorn[standard]>=0.30.0     # Server ASGI berperforma tinggi
pydantic>=2.8.0               # Validasi data & schema parsing
pydantic-settings>=2.4.0      # Pengelolaan konfigurasi environment terisolasi
pydantic-ai>=0.0.18           # Abstraksi agen LLM berbasis structured output
langgraph>=0.2.20             # State machine & routing graph multi-agent
langchain-core>=0.3.0         # Komponen dasar LangChain
langchain-google-genai>=2.0.0 # Integrasi model Gemini dalam LangChain
google-genai>=0.1.1           # SDK resmi Google GenAI API (Gemini 3.5 & Embeddings)
supabase>=2.6.0               # Client Python Supabase (PostgREST, Auth, Storage)
httpx>=0.27.0                 # HTTP client asynchronous non-blocking
python-dotenv>=1.0.1          # Pembaca berkas konfigurasi .env lokal
python-multipart>=0.0.9       # Parser form data & file upload untuk FastAPI
```

---

### 4.4 Kebutuhan Akun & API Keys Eksternal (API Credentials)

Aplikasi membutuhkan kredensial pihak ketiga yang harus didefinisikan pada berkas [`.env`](file:///e:/wa%20bot%20longchain/.env):

| Nama Variabel Lingkungan | Sumber Kredensial | Deskripsi & Kegunaan |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) | Kunci akses model Gemini 3.5 Flash Vision dan Gemini-Embedding-001. |
| `SUPABASE_URL` | [Supabase Dashboard](https://supabase.com/) | URL endpoint proyek Supabase (contoh: `https://xxxx.supabase.co`). |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard (`API Settings`) | Service role secret key (`sb_secret_...` atau JWT) untuk bypass RLS pada ingestion dan audit. |
| `SUPABASE_BUCKET_NAME` | Supabase Storage | Nama bucket penyimpanan foto keluhan petani (default: `crop-symptoms`). |
| `WEATHER_API_KEY` | [WeatherAPI.com](https://www.weatherapi.com/) | API Key cuaca (Aktif: `76d7a4136a6948e8ac464008250810`). |
| `WHATSAPP_PROVIDER` | Internal Config | Menentukan provider aktif: `waha` atau `meta` (default: `waha`). |
| `WAHA_BASE_URL` | Docker Bridge Network | URL endpoint WAHA (contoh: `http://localhost:3000` di lokal, atau `http://waha:3000` di Docker). |
| `WAHA_SESSION` | WAHA Dashboard | Nama sesi WhatsApp yang digunakan (default: `chatbot` atau `default`). |
| `ADMIN_API_KEY` | Internal Config | Kunci otentikasi header `X-Admin-Key` untuk portal admin & PPL. |
| `CONFIDENCE_THRESHOLD` | Internal Config | Ambang batas kepastian diagnosa bot (default: `0.70` atau 70%). |
| `META_WA_PHONE_NUMBER_ID` | [Meta for Developers](https://developers.facebook.com/) | *(Opsional)* ID Nomor Telepon WhatsApp Cloud API resmi. |
| `META_WA_ACCESS_TOKEN` | Meta for Developers | *(Opsional)* Token akses Graph API Meta permanent. |
| `META_WA_VERIFY_TOKEN` | Meta for Developers | *(Opsional)* Token verifikasi handshake webhook (`GET /webhook`). |

---

### 4.5 Kebutuhan Port & Jaringan (Network & Ports)

- **Port `8000` (FastAPI Server)**: Harus dapat diakses oleh WAHA (atau internet/reverse proxy) untuk menerima webhook `POST /webhook` dan menyediakan Swagger docs `/docs`.
- **Port `3000` (WAHA Server)**: Digunakan untuk membuka dashboard WAHA (`http://localhost:3000/dashboard`) guna melakukan scan QR Code WhatsApp dan memantau status sesi.
- **Port `443` (Outbound HTTPS)**: Server wajib memiliki izin keluar (*egress*) ke:
  - `generativelanguage.googleapis.com` (Google Gemini API).
  - `*.supabase.co` (Supabase Database, REST & Storage).
  - `api.weatherapi.com` (WeatherAPI.com).
  - `api.open-meteo.com` & `geocoding-api.open-meteo.com` (Open-Meteo).

---

### 4.6 Prasyarat Database & Storage Supabase

Sebelum aplikasi dijalankan untuk pertama kali, Supabase harus dipersiapkan dengan langkah berikut:
1. **Aktifkan Ekstensi `vector`**: Melalui SQL Editor dengan perintah `CREATE EXTENSION IF NOT EXISTS vector;`.
2. **Jalankan Skrip DDL**: Eksekusi seluruh isi berkas [`database/schema.sql`](file:///e:/wa%20bot%20longchain/database/schema.sql) untuk membentuk tabel `knowledge_base`, `disease_reference_images`, `consultation_audits`, `chat_sessions`, `market_prices`, dan fungsi RPC `match_knowledge`.
3. **Buat Dua Storage Bucket Publik**:
   - Bucket **`crop-symptoms`**: Akses **Public** (untuk foto keluhan fisik dari petani).
   - Bucket **`disease-references`**: Akses **Public** (untuk 292 foto dataset resmi pembanding).
4. **Jalankan Skrip Ingestion**:
   - `python data/ingest_knowledge.py` (untuk mengindeks 11 penyakit ke pgvector).
   - `python data/upload_dataset_to_supabase.py` (untuk mengunggah 292 foto dataset).

---

## 🌟 5. Rincian Fitur yang Sudah Dibuat & Berfungsi

Berikut adalah rekapitulasi seluruh modul dan fungsionalitas yang telah diimplementasikan dalam kode:

### 1. Konsultasi Teks Berbasis RAG Semantik (11 Penyakit Utama)
- **Komoditas Cabai (6 Penyakit)**:
  1. *Antraknosa / Patek* (*Colletotrichum capsici*)
  2. *Penyakit Bulai / Virus Kuning Gemini* (Gemini Virus)
  3. *Layu Bakteri* (*Ralstonia solanacearum*)
  4. *Layu Fusarium* (*Fusarium oxysporum*)
  5. *Serangan Hama Thrips / Keriting Daun* (*Thrips parvispinus*)
  6. *Bercak Daun Cercospora / Mata Katak* (*Cercospora capsici*)
- **Komoditas Padi (5 Penyakit/Hama)**:
  1. *Penyakit Blas Daun & Blas Leher* (*Magnaporthe oryzae*)
  2. *Hawar Daun Bakteri / Kresek* (*Xanthomonas oryzae*)
  3. *Penggerek Batang Padi / Sundep & Beluk* (*Scirpophaga innotata*)
  4. *Penyakit Tungro* (Rice Tungro Bacilliform/Spherical Virus)
  5. *Wereng Batang Coklat / WBC* (*Nilaparvata lugens*)
- **Format Output 3 Pilar**: Setiap jawaban diagnosa terstruktur menyajikan:
  - Identifikasi nama penyakit & nama patogen ilmiah.
  - Penjelasan gejala klinis.
  - **Pilar 1: Tindakan Fisik / Mekanis** (pemangkasan, eradikasi tanaman sakit).
  - **Pilar 2: Sanitasi Lahan & Drainase** (pengaturan kelembapan, bedengan).
  - **Pilar 3: Rekomendasi Bahan Aktif Kimiawi Terdaftar** (golongan azol, tembaga, mankozeb, klorantraniliprol, dll.) dengan dosis dan cara rotasi untuk mencegah resistensi.

### 2. Konsultasi Foto Multimodal Vision (Computer Vision)
- Petani dapat langsung mengirimkan foto gejala daun, buah, atau tanaman sakit ke nomor WhatsApp.
- Bot secara otomatis menangani foto **tanpa caption teks** dengan menyuntikkan prompt default: *"Tolong diagnosa gejala penyakit tanaman pada foto ini."*.
- **Guardrail Pembatasan Komoditas**: Bot menganalisis apakah foto merupakan tanaman Cabai atau Padi. Jika pengguna mengirimkan foto tanaman lain (misal sawit, apel, kopi, atau benda mati), bot secara tegas dan sopan menolak berspekulasi demi menjaga integritas data pertanian.
- Foto yang dikirimkan diunduh dari WhatsApp dan diarsipkan otomatis ke **Supabase Storage** pada bucket `crop-symptoms`.
- Output dilengkapi **Link Foto Pembanding Resmi** dari dataset agar petani dapat mencocokkan visual penyakit mereka dengan foto referensi laboratorium.

### 3. Dataset Foto Referensi Penyakit (292 Foto Terkatalog)
- Seluruh 292 gambar dari direktori lokal `data/dataset_foto` telah diunggah ke Supabase Storage pada bucket `disease-references`.
- Metadata gambar (nama penyakit, komoditas, URL publik, deskripsi visual) tercatat rapi di tabel `disease_reference_images`.
- Saat diagnosa dihasilkan, bot melakukan pencarian foto pembanding yang relevan dan menyertakan tautan foto resolusi tinggi ke dalam pesan balasan WhatsApp.

### 4. Prakiraan Cuaca Pertanian & Kalender Semprot (Weather Advisory)
- **Engine Cuaca**: Menggunakan **WeatherAPI.com** (Key: `76d7a4136a6948e8ac464008250810`) dengan geocoding otomatis kota/kabupaten di Indonesia dan parameter bahasa Indonesia.
- **Auto Fallback**: Apabila koneksi WeatherAPI bermasalah atau kuota bulanan terlampaui, sistem otomatis berpindah (*fallback*) ke **Open-Meteo API** tanpa downtime.
- **Advisory Penyemprotan & Pemupukan**:
  - Peringatan jika peluang hujan tinggi (>50%) atau presipitasi >0.5 mm: Menginstruksikan petani untuk menunda aplikasi pestisida agar bahan aktif tidak terbuang percuma tercuci hujan.
  - Peringatan kelembapan tinggi (>85%): Memberikan panduan penggunaan perekat (*adjuvant*) untuk antisipasi spora jamur antraknosa/blas.
  - Waktu optimal aplikasi: Memberikan saran jam terbaik penyemprotan (06.30 - 09.00 pagi atau sore hari saat stomata terbuka).

### 5. Informasi & Fluktuasi Harga Pasar Komoditas
- Menyediakan acuan harga komoditas utama: Cabai Rawit Merah, Cabai Merah Keriting, Gabah Kering Panen (GKP), dan Beras Medium.
- Membedakan antara **Harga di Tingkat Petani / Kebun (*Farmgate Price*)** dan **Harga di Tingkat Pasar Konsumen**.
- Dilengkapi dengan *tips negosiasi pasar* agar petani tidak dirugikan oleh tengkulak.
- **Admin Override**: Admin atau dinas pertanian dapat memperbarui acuan harga harian secara dinamis via REST API tanpa perlu mengubah kode sumber.

### 6. Rekomendasi Dosis Pupuk & Nutrisi Spesifik
- Rekomendasi terpisah berdasarkan **Fase Pertumbuhan**:
  - *Fase Vegetatif* (Pertumbuhan Daun & Akar): Fokus pada N-P (Urea, NPK 16-16-16, pupuk hayati).
  - *Fase Generatif* (Pembungaan & Pengisian Buah/Bulir): Fokus pada K-P-Ca-Si (KNO3 Putih, MKP, Kalsium Boron, Silika untuk ketahanan bulir padi dan pencegahan kerontokan bunga cabai).
- Dilengkapi petunjuk teknis aplikasi (kocor vs tabur vs semprot daun) dan pestisida pendamping berimbang.

### 7. Rekam Jejak / Riwayat Konsultasi Petani
- Petani dapat mengetik *"riwayat"* di WhatsApp kapan saja.
- Bot mengambil data dari tabel `consultation_audits` berdasarkan nomor WhatsApp pengirim dan menampilkan rekam jejak diagnosa sebelumnya, persentase keyakinan, tanggal konsultasi, serta status rujukan PPL.

### 8. Portal Administrasi & Rujukan PPL (REST API)
- Dilindungi oleh pengaman header `X-Admin-Key`.
- **Manajemen Harga Pasar (Full CRUD)**:
  - `POST /api/v1/admin/prices`: Menambahkan harga harian komoditas baru.
  - `GET /api/v1/admin/prices`: Menampilkan daftar harga harian per provinsi.
  - `PUT /api/v1/admin/prices/{id}`: Mengubah data harga.
  - `DELETE /api/v1/admin/prices/{id}`: Menghapus data harga.
- **Monitoring & Audit Konsultasi Petani**:
  - `GET /api/v1/admin/consultations`: Melihat seluruh daftar pertanyaan dan foto yang masuk dari petani (dapat difilter khusus yang berstatus `is_referred_to_ppl = true`).
  - `PATCH /api/v1/admin/consultations/{id}`: Petugas PPL dapat memperbarui catatan penanganan lapangan atau mencatat bahwa masalah petani telah dikunjungi/ditindaklanjuti.
  - `DELETE /api/v1/admin/consultations/{id}`: Menghapus data spam atau uji coba.

### 9. Dual WhatsApp Gateway (WAHA & Meta Cloud API)
- **WAHA (WhatsApp HTTP API)**: Menjalankan engine `WEBJS` melalui container Docker headless browser. Memungkinkan bot terhubung ke nomor WhatsApp reguler/bisnis tanpa biaya per pesan dari Meta. Mendukung pengiriman teks dan pengunduhan media foto.
- **Meta WhatsApp Cloud API**: Kode juga telah terstruktur dengan endpoint resmi Meta Graph API (`v20.0`) lengkap dengan verifikasi webhook (`GET /webhook` handshake) jika sewaktu-waktu ingin beralih ke jalur WhatsApp Business Enterprise resmi.

---

## 📊 6. Skema Basis Data & Konfigurasi Supabase

TaniPintar menggunakan PostgreSQL di Supabase dengan ekstensi `vector`. Berikut ringkasan tabel dan fungsinya:

| Nama Tabel | Tipe Data Utama | Deskripsi & Fungsi |
| :--- | :--- | :--- |
| **`knowledge_base`** | `id`, `commodity`, `disease_name`, `scientific_name`, `pathogen_type`, `symptoms`, `mechanical_treatment`, `sanitation_treatment`, `chemical_actives`, `prevention`, `embedding (vector 768)` | Menyimpan pustaka 11 penyakit tanaman cabai dan padi beserta embedding vektor untuk pencarian semantik RAG. Menggunakan indeks `IVFFlat` (`vector_cosine_ops`). |
| **`disease_reference_images`**| `id`, `commodity`, `disease_name`, `image_url`, `description`, `created_at` | Katalog 292 tautan foto referensi resmi penyakit dari dataset lapangan yang tersimpan di Supabase Storage. |
| **`consultation_audits`** | `id (UUID)`, `phone_number`, `crop_type`, `suspected_disease`, `confidence_score`, `is_referred_to_ppl`, `media_url`, `farmer_query`, `bot_recommendation (JSONB)`, `created_at` | Audit trail lengkap seluruh konsultasi petani, bukti foto gejala fisik, serta status rujukan ke petugas PPL lapangan. |
| **`chat_sessions`** | `phone_number (PK)`, `current_state (JSONB)`, `last_crop_context`, `updated_at` | Menyimpan memori percakapan jangka pendek petani agar bot mengingat komoditas tanaman yang sedang dibahas. |
| **`market_prices`** | `id`, `price_date`, `commodity`, `province`, `farmgate_price`, `consumer_price`, `unit`, `source`, `notes` | Menyimpan data acuan harga pasar harian komoditas pangan per wilayah. |

### Fungsi RPC PostgreSQL: `match_knowledge`
Fungsi stored procedure di database untuk menghitung kesamaan kosinus (*Cosine Distance*):
```sql
SELECT 
    kb.id, kb.commodity, kb.disease_name, kb.scientific_name, kb.pathogen_type,
    kb.symptoms, kb.mechanical_treatment, kb.sanitation_treatment, kb.chemical_actives,
    kb.prevention,
    1 - (kb.embedding <=> query_embedding) AS similarity
FROM knowledge_base kb
WHERE (filter_commodity IS NULL OR LOWER(kb.commodity) = LOWER(filter_commodity))
  AND (1 - (kb.embedding <=> query_embedding)) >= match_threshold
ORDER BY kb.embedding <=> query_embedding
LIMIT match_count;
```

---

## 🛡️ 7. Mekanisme Guardrail & Keselamatan Agronomi

Pertanian adalah sektor berisiko tinggi. Kesalahan rekomendasi dosis atau diagnosis dapat menyebabkan kegagalan panen. Oleh karena itu, TaniPintar menerapkan prinsip kehati-hatian ketat:

1. **Ambang Batas Keyakinan (*Confidence Threshold* $\ge 0.70$)**:
   - Jika hasil inferensi AI memiliki tingkat kepastian di bawah 70% ($< 0.70$), sistem **secara otomatis menolak memberikan diagnosis spekulatif**.
   - Sistem akan mengaktifkan *Safe Fallback Message*:
     > *"Gejala pada tanaman Anda belum dapat diidentifikasi dengan tingkat kepastian yang memadai. Untuk menghindari kesalahan penanganan yang merugikan, kami merekomendasikan Anda berkonsultasi langsung dengan Petugas Penyuluh Lapangan (PPL) di BPP setempat atau membawa sampel tanaman ke pos penyuluhan terdekat."*
2. **Pembatasan Spesialisasi Komoditas (*Crop Restriction Guardrail*)**:
   - Bot menolak secara halus jika ditanya mengenai tanaman di luar Cabai dan Padi (misalnya sawit, durian, karet) untuk memastikan saran yang diberikan selalu akurat dan berbasis data teruji.
3. **Pemberian Pilihan Bahan Kimia Sebagai Opsi Terakhir**:
   - Format jawaban selalu menempatkan tindakan mekanis dan sanitasi di urutan teratas (Pilar 1 dan 2) sebelum merekomendasikan bahan kimiawi (Pilar 3), sejalan dengan prinsip Pengendalian Hama Terpadu (PHT) Kementerian Pertanian RI.

---

## 🧪 8. Hasil Pengujian Kualitas (Testing & QA)

Sistem telah dilengkapi dengan automated test suites yang mencakup pengujian unit dan integrasi:

| Berkas Pengujian | Jumlah Test | Komponen yang Diuji | Status |
| :--- | :---: | :--- | :---: |
| `tests/test_tani_pintar.py` | 7 Tests | Routing intent, RAG text diagnosis, Guardrail confidence threshold, Gemini Vision, kalkulasi harga pasar, rekomendasi pupuk, dan cuaca. | ✅ **100% Passed** |
| `tests/test_api_endpoints.py`| 6 Tests | Endpoint Healthcheck (`/health`), Webhook verification token handshake, Webhook async message receiver, Admin CRUD Market Prices, Admin CRUD Consultation Audits. | ✅ **100% Passed** |
| **Total Test Suites** | **13 Tests** | **End-to-End System Integrity** | **SEMUA LOLOS (0 Error)** |

---

## ⚠️ 9. Apa yang Belum Ditambahkan & Kekurangan Sistem Saat Ini (Gaps & Backlog)

Meskipun sistem inti (core engine), basis data, kecerdasan buatan, dan gateway WhatsApp sudah berjalan 100%, terdapat beberapa aspek dan fitur lanjutan yang **belum ditambahkan** atau **dapat ditingkatkan** menuju sistem skala produksi komersial (*enterprise-scale*):

---

### 9.1 Kekurangan Fitur & Kebutuhan Pengembangan Lanjutan

#### 1. Belum Ada Tampilan Antarmuka Web Visual untuk Dashboard Admin & PPL (Frontend UI)
* **Kondisi Saat Ini**: Portal Admin dan PPL saat ini baru tersedia dalam bentuk **REST API** yang diakses melalui Swagger UI (`http://localhost:8000/docs`) atau API Client (Postman/Curl).
* **Kebutuhan**: Petugas PPL di lapangan dan dinas pertanian membutuhkan antarmuka web modern (*Web Dashboard* berbasis Next.js/React/Vite) dengan tampilan visual yang intuitif, seperti:
  - Galeri peninjauan foto-foto penyakit tanaman yang baru dikirim petani.
  - Tombol satu-klik untuk merespons atau mengirim catatan tindak lanjut rujukan ke WhatsApp petani.
  - Peta sebaran spasial (GIS Map) serangan hama per kecamatan/desa untuk mendeteksi *outbreak* (ledakan populasi wereng atau antraknosa).

#### 2. Sumber Harga Pasar Masih Menggunakan Simulasi & Input Manual Admin (Belum Web Scraping Otomatis)
* **Kondisi Saat Ini**: Modul harga pasar saat ini berjalan menggunakan kombinasi acuan harga rata-rata nasional dengan fluktuasi harian dan input override manual oleh admin via REST API.
* **Kebutuhan**: Belum ada koneksi scraper otomatis ke API/Portal publik resmi pemerintah seperti:
  - Panel Harga Badan Pangan Nasional (Bapanas) (`panelharga.badanpangan.go.id`).
  - Pusat Informasi Harga Pangan Strategis Nasional (PIHPS) Bank Indonesia.
  - Integrasi ini akan membuat harga ter-update otomatis setiap pukul 10.00 WIB tanpa campur tangan admin.

#### 3. Belum Ada Fitur Notifikasi Proaktif (*Push Broadcast Notification / Peringatan Dini*)
* **Kondisi Saat Ini**: Bot bersifat **reaktif** (hanya merespons ketika petani mengirim pesan terlebih dahulu).
* **Kebutuhan**: Fitur *Early Warning System (EWS)* berupa pesan proaktif terjadwal (*Scheduled Cron Job*) ke seluruh petani yang terdaftar:
  - Peringatan cuaca ekstrem: *"Peringatan BMKG: Wilayah Karawang diprediksi hujan lebat disertai angin 3 hari ke depan, segera perbaiki drainase sawah Anda."*
  - Notifikasi serangan hama musiman pada fase tanam tertentu.

#### 4. Belum Mendukung Pesan Suara (*Voice Note / Audio Processing*)
* **Kondisi Saat Ini**: Bot hanya menerima input berupa **teks** dan **gambar/foto**.
* **Kebutuhan**: Banyak petani pedesaan yang lebih nyaman berbicara mengirim *Voice Note* di WhatsApp daripada mengetik teks panjang di layar ponsel.
  - Diperlukan integrasi model *Speech-to-Text (STT)* seperti Whisper API atau Gemini Audio Transcription untuk mentranskripsi pesan suara petani menjadi teks sebelum diproses oleh LangGraph.
  - Respon suara balasan (*Text-to-Speech / TTS*) untuk petani tuna aksara atau lansia.

#### 5. Belum Mendukung Dialek & Bahasa Daerah Secara Penuh
* **Kondisi Saat Ini**: Sistem merespons dalam Bahasa Indonesia yang santun dan semi-formal. Walaupun bot mengenali istilah teknis lokal (seperti *patek, sundep, beluk, kresek, asem-aseman*), bot belum mampu merespons penuh dalam bahasa daerah seperti Bahasa Jawa (Ngoko/Kromo) atau Bahasa Sunda.
* **Kebutuhan**: Kemampuan deteksi bahasa daerah otomatis dan opsi preferensi bahasa pengguna (*Language Selector: Indonesia, Jawa, Sunda*).

#### 6. Ruang Lingkup Komoditas Masih Terbatas (Khusus Cabai & Padi)
* **Kondisi Saat Ini**: Sistem dibatasi secara ketat (*guardrail*) hanya untuk 2 komoditas (Cabai dan Padi).
* **Kebutuhan**: Memperluas pustaka pengetahuan (*Knowledge Base*) ke komoditas bernilai tinggi lainnya:
  - Bawang Merah (Ulat Grayak, Moler/Fusarium).
  - Jagung (Ulat Grayak Frugiperda/FAW, Bulai).
  - Kedelai dan Tomat.

#### 7. Belum Menggunakan Visual Vector Search (Image Embedding)
* **Kondisi Saat Ini**: Pencarian RAG hanya dilakukan pada **teks** menggunakan `gemini-embedding-001`. Foto fisik didiagnosa langsung oleh model Large Multimodal Model (Gemini Vision).
* **Kebutuhan**: Menerapkan *Image Embedding Model* (seperti CLIP / SigLIP / BioCLIP) untuk meng-vektor-kan foto fisik langsung ke Supabase `vector`, sehingga foto petani bisa langsung dicocokkan tingkat kemiripan fiturnya secara matematis terhadap 292 foto dataset referensi di database sebelum diproses LLM.

#### 8. Belum Ada Pengelolaan Kelompok Tani (Multi-Tenancy Gapoktan)
* **Kondisi Saat Ini**: Database mencatat data per nomor telepon individual, belum mengelompokkan petani berdasarkan wilayah *Gapoktan* (Gabungan Kelompok Tani), Koperasi Unit Desa (KUD), atau Balai Penyuluhan Pertanian (BPP) tertentu.

---

## 🗺️ 10. Rekomendasi Rencana Aksi (Roadmap Pengembangan)

Berikut adalah tahapan rekomendasi pengembangan berikutnya:

```mermaid
gantt
    title Roadmap Pengembangan TaniPintar Bot
    dateFormat  YYYY-MM-DD
    section Fase 1 (Segera)
    Pembuatan Web Dashboard PPL (React/Next.js)      :2026-10-05, 20d
    Scraper Otomatis Panel Harga Bapanas              :2026-10-15, 15d
    section Fase 2 (Jangka Menengah)
    Integrasi Voice Note WhatsApp (Whisper/Gemini)   :2026-11-01, 25d
    Sistem Peringatan Dini (EWS Push Broadcast)      :2026-11-15, 20d
    Ekspansi Komoditas Bawang Merah & Jagung          :2026-12-01, 30d
    section Fase 3 (Skala Nasional)
    Multi-Tenancy Kelompok Tani & Koperasi            :2027-01-01, 40d
    Visual Similarity Search (CLIP / Image Vector)    :2027-01-20, 30d
```

### Tahap 1: Penguatan Antarmuka & Otomasi Data (1 Bulan ke Depan)
1. Membangun **Web Portal Admin & PPL** sederhana berbasis frontend modern agar petugas penyuluh dapat memantau konsultasi petani tanpa menyentuh Swagger API.
2. Mengintegrasikan script background cron untuk menarik data harga resmi dari portal Bapanas setiap pagi.

### Tahap 2: Aksesibilitas Petani Pedesaan (2 - 3 Bulan ke Depan)
1. Mengaktifkan kemampuan transkripsi **WhatsApp Voice Note** agar petani cukup berbicara di mikrofon ponsel mereka.
2. Menambahkan fitur broadcast informasi cuaca buruk otomatis ke petani di zona koordinat rawan banjir/kekeringan.

### Tahap 3: Skalabilitas Komoditas & Ekosistem (3 - 6 Bulan ke Depan)
1. Menambahkan dataset 5 penyakit Bawang Merah dan 4 penyakit Jagung ke dalam Supabase pgvector.
2. Mengembangkan modul manajemen Kelompok Tani (*Gapoktan*) untuk pelaporan panen massal ke dinas pertanian daerah.

---

## 📋 11. Struktur Berkas Proyek Saat Ini

```text
e:/wa bot longchain/
├── agents/                           # PydanticAI Agents & Skema Logika
│   ├── diagnosis_agent.py           # RAG Text Engine & Gemini 3.5 Flash Vision
│   ├── fertilizer_agent.py          # Logika Formulasi Dosis & Nutrisi Tanaman
│   ├── market_agent.py              # Logika Acuan Harga Komoditas
│   ├── prompts.py                   # System Prompts & Guardrail Fallback
│   └── schemas.py                   # Pydantic Schemas untuk Validasi Output
│
├── api/                              # Lapisan REST API & Webhook (FastAPI)
│   ├── app.py                       # App Factory, CORS, Lifecycle Startup
│   └── routes/
│       ├── admin.py                 # Endpoint CRUD Harga Pasar & Rujukan PPL
│       ├── health.py                # Healthcheck Endpoint (/health)
│       └── whatsapp.py              # Handler Pesan & Foto WhatsApp (WAHA / Meta)
│
├── core/                             # Konfigurasi & Utilitas Inti
│   ├── config.py                    # Pydantic Settings & Environment Variables
│   └── logger.py                    # Structured UTF-8 Logger
│
├── data/                             # Dataset & Skrip Ingestion
│   ├── dataset_foto/                # 292 Foto Lapangan Asli (Cabai & Gejala)
│   ├── knowledge/                   # Basis Pengetahuan 11 Penyakit (JSON)
│   │   ├── cabai_diseases.json      # 6 Penyakit Utama Cabai
│   │   └── padi_diseases.json       # 5 Penyakit Utama Padi
│   ├── ingest_knowledge.py          # Skrip Vector Indexing ke Supabase pgvector
│   └── upload_dataset_to_supabase.py # Skrip Pengunggah 292 Foto ke Storage & DB
│
├── database/                         # Database Access Layer
│   ├── repository.py                # Operasi CRUD Relasional & RPC Vektor
│   ├── schema.sql                   # Skrip DDL PostgreSQL + pgvector
│   └── supabase_client.py           # Supabase Client Singleton
│
├── services/                         # Integrasi Layanan Eksternal
│   ├── price_service.py             # Layanan Harga Komoditas Petani vs Pasar
│   ├── storage_service.py           # Pengunggah Media ke Supabase Storage
│   ├── weather_service.py           # WeatherAPI.com + Fallback Open-Meteo
│   └── whatsapp_service.py          # Pengirim Pesan & Pengunduh Media WhatsApp
│
├── tests/                            # Automated Test Suites
│   ├── test_api_endpoints.py        # Uji Endpoint Webhook & Admin Portal
│   └── test_tani_pintar.py          # Uji Komprehensif 6 Fitur MVP & Guardrail
│
├── .env                             # Environment Variables Rahasia (API Keys)
├── .env.example                     # Template Variabel Lingkungan
├── .gitignore                       # Proteksi Berkas Git (Abaikan waha_data, logs)
├── docker-compose.yml               # Orkestrasi Docker (tanipintar-bot & waha)
├── Dockerfile                       # Container Build Recipe Python 3.12
├── graph_builder.py                 # LangGraph StateGraph Kompilasi 6 Layanan
├── main.py                          # Uvicorn Server Entrypoint
├── pyproject.toml                   # Konfigurasi Proyek & Dependensi
├── requirements.txt                 # Dependensi PIP
└── laporan.md                       # Dokumen Laporan Ini
```

---

## 🏁 12. Kesimpulan

Proyek **TaniPintar Bot** telah berhasil mencapai status operasional fungsional penuh (*production-ready core*). Seluruh fondasi arsitektur—mulai dari RAG semantik berkecepatan tinggi, analisis multimodal foto lapangan, sistem cuaca pertanian cerdas dengan WeatherAPI, proteksi guardrail keselamatan, hingga integrasi WhatsApp live dengan WAHA—telah terpasang dan teruji secara menyeluruh.

Dokumen ini menjadi rujukan resmi bagi arsitektur teknis saat ini serta panduan peta jalan (*roadmap*) bagi tim pengembang untuk merealisasikan fitur-fitur lanjutan ke depan.
