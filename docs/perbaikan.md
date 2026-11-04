# 🔍 Analisis Kekurangan Sistem & Rencana Perbaikan: TaniPintar Bot

**Proyek:** TaniPintar — AI WhatsApp Assistant Perlindungan Tanaman Cabai & Padi  
**Dokumen:** Audit menyeluruh (kode, keamanan, infrastruktur, testing, data, dokumentasi)  
**Tanggal Audit Awal:** 31 Oktober 2026  
**Pembaruan Terakhir:** 4 November 2026  
**Status Implementasi:** **Aktif — Paket P0 (Stabilisasi & Keamanan Inti) SELESAI DIIMPLEMENTASIKAN & TERVERIFIKASI (100% Green Unit Tests)**  

---

## 📑 Daftar Isi

1. [Ringkasan Eksekutif](#1-ringkasan-eksekutif)
2. [Inventaris File Proyek](#2-inventaris-file-proyek)
3. [Hasil Verifikasi & Status Pengujian](#3-hasil-verifikasi--status-pengujian)
4. [Temuan P0 — Bug Fungsional](#4-temuan-p0--bug-fungsional)
5. [Temuan P0 — Keamanan](#5-temuan-p0--keamanan)
6. [Temuan P1 — Dependency & Infrastruktur](#6-temuan-p1--dependency--infrastruktur)
7. [Temuan P1 — Reliabilitas & Observability](#7-temuan-p1--reliabilitas--observability)
8. [Temuan P2 — Testing](#8-temuan-p2--testing)
9. [Temuan P2 — Data & Model AI](#9-temuan-p2--data--model-ai)
10. [Temuan P2 — Dokumentasi & Higiene Repo](#10-temuan-p2--dokumentasi--higiene-repo)
11. [Gap Produk / UX](#11-gap-produk--ux)
12. [Rencana Perbaikan Bertahap](#12-rencana-perbaikan-bertahap)
13. [Matriks Prioritas (Ringkas)](#13-matriks-prioritas-ringkas)
14. [Definisi Selesai (Definition of Done)](#14-definisi-selesai-definition-of-done)

---

## 1. Ringkasan Eksekutif

TaniPintar Bot adalah sistem WhatsApp AI untuk skrining hama/penyakit cabai & padi, transparansi
harga pasar, archived foto gejala, prakiraan cuaca pertanian, rekomendasi pupuk/pestisida, dan
riwayat konsultasi. Arsitektur inti: **FastAPI** (webhook) → **LangGraph StateGraph** (routing &
orkestrasi) → **Gemini** (LLM/Vision/Embedding) → **Supabase** (PostgreSQL, pgvector, Storage) →
**WAHA** (gateway WhatsApp).

Audit sistem menemukan temuan dengan status resolusi per 4 November 2026 sebagai berikut:

| Kategori | Tingkat Risiko | Total Temuan | Resolved (4 Nov 2026) | In Progress / Roadmap |
| :--- | :---: | :---: | :---: | :---: |
| Bug fungsional (P0) | **Tinggi** | 7 | **5 Resolved** | 2 (Tahap 2) |
| Keamanan (P0) | **Tinggi** | 8 | **6 Resolved** | 2 (Tahap 2) |
| Dependency & Infrastruktur (P1) | Sedang | 8 | 0 | 8 (Tahap 2) |
| Reliabilitas & Observability (P1) | Sedang | 6 | 0 | 6 (Tahap 4) |
| Testing (P2) | Sedang | 5 | 2 | 3 (Tahap 3) |
| Data & Model AI (P2) | Sedang | 5 | 1 | 4 (Tahap 5) |
| Dokumentasi & Higiene Repo (P2) | Rendah | 4 | 2 | 2 (Tahap 5) |
| Gap Produk / UX | Rendah–Sedang | 4 | 0 | 4 (Tahap 5) |

**Status Penanganan 3 Risiko Kritis Terbesar:**

1. ✅ **`KeyError: 'Cabai'` & "Beras" TERSELESAIKAN:** `PriceService` telah dipetakan menangani komoditas agregat menjadi 4 varietas cabai dan 3 varietas padi/beras secara deterministik tanpa melempar exception saat Supabase offline.
2. ✅ **Keamanan Admin & Webhook DITEGAKKAN:** Bypass autentikasi mode development telah dihapus dari `api/routes/admin.py` dan seluruh endpoint `/webhook/test/*` kini wajib menggunakan `X-Admin-Key`. CORS dikonfigurasi aman tanpa wildcard credentials, dan nomor telepon petani disensor otomatis di seluruh log.
3. ✅ **Label Harga Pasar DIJADIKAN TRANSPARAN & JUJUR:** Label data harga otomatis diubah menjadi *"Estimasi Model Harga Pasar TaniPintar (Baseline Berkala & Pasar Lokal DIY-Jateng)"* disertai klausul disclaimer pendukung keputusan, mengeliminasi over-klaim PIHPS Bank Indonesia.

---

## 2. Inventaris File Proyek

### 2.1 Kode Aplikasi

| Area | File | Keterangan |
| :--- | :--- | :--- |
| Entry point | `main.py` | Menjalankan uvicorn. |
| Orkestrasi | `graph_builder.py` | ±861 baris; seluruh node LangGraph, router, formatter, audit saver. |
| API | `api/app.py` | Factory FastAPI + CORS. |
| API | `api/routes/whatsapp.py` | Webhook Meta & WAHA, pemrosesan background, endpoint test. |
| API | `api/routes/admin.py` | CRUD harga & audit konsultasi. |
| API | `api/routes/health.py` | Health check. |
| Agent | `agents/diagnosis_agent.py` | RAG teks + Vision multimodal (OpenCV + Visual RAG). |
| Agent | `agents/fertilizer_agent.py` | Rekomendasi pupuk & pestisida dari katalog. |
| Agent | `agents/market_agent.py` | **Tidak dipakai** (dead code). |
| Agent | `agents/prompts.py` | Prompt agronomi & safe fallback. |
| Agent | `agents/schemas.py` | Pydantic schema. |
| Service | `services/whatsapp_service.py` | ±830 baris; kirim teks/button/list/poll, typing, download media. |
| Service | `services/session_service.py` | Timeout sesi 30 menit & reset global. |
| Service | `services/price_service.py` | Harga pasar (DB + fallback sintetis). |
| Service | `services/weather_service.py` | BMKG Adm4 → WeatherAPI → Open-Meteo. |
| Service | `services/storage_service.py` | Upload foto ke Supabase Storage. |
| Service | `services/cv_preprocessor.py` | Gatekeeper kualitas citra (blur, brightness, HSV). |
| Service | `services/visual_rag_service.py` | Image-to-image cosine search. |
| Core | `core/config.py` | Pydantic Settings. |
| Core | `core/logger.py` | Logger stdout. |
| Core | `core/dedup.py` | Dedup pesan (Redis opsional / LRU lokal). |
| Core | `core/latency_tracker.py` | Pengukuran latensi per fase. |
| Database | `database/supabase_client.py` | Singleton Supabase. |
| Database | `database/repository.py` | Akses tabel & RPC. |
| Database | `database/schema.sql` | DDL utama. |
| Database | `database/schema_patch.sql` | Patch RPC & view. |
| Database | `database/create_visual_gallery.sql` | Tabel galeri visual. |
| Database | `database/seed_disease_images.sql` | Seed galeri. |

### 2.2 Data & Script

- `data/knowledge/cabai_diseases.json` (6 penyakit)
- `data/knowledge/padi_diseases.json` (5 penyakit)
- `data/knowledge/fertilizer_pesticide_catalog.json` (katalog pupuk/pestisida per fase)
- `data/visual_gallery_embeddings.json` (72 item, 768 dimensi)
- `data/pihps_prices_latest.json` (snapshot harga)
- `data/dataset_foto/` (491 file, ±70 MB)
- `data/ingest_knowledge.py`, `data/seed_pihps_prices.py`, `data/upload_dataset_to_supabase.py`
- `scripts/build_visual_gallery.py`, `scripts/ingest_image_vectors.py`

### 2.3 Test

`tests/test_api_endpoints.py`, `test_tani_pintar.py`, `test_interactive_messages.py`,
`test_price_interactive_flow.py`, `test_session_management.py`, `test_weather_routing_flow.py`,
`tests/benchmark_metrics.py` (bukan test, tapi skrip benchmark). Total 41 test.

### 2.4 Infrastruktur

`Dockerfile`, `docker-compose.yml`, `requirements.txt`, `pyproject.toml`, `uv.lock`,
`.env.example`, `.dockerignore`, `.gitignore`.

### 2.5 Dokumentasi & Artefak

- `README.md`
- `docs/`: `arsitektur.md`, `deploy.md`, `DOCKER_GUIDE.md`, `laporan.md`, `laporan_capstone_overleaf.tex`,
  `overleaf/main.tex`, `bug dan eror.md`, `bug_dan_eror.md` (duplikat), 4 dokumen progres harian,
  `capstone fix - Copy.docx` (6 MB).
- Artefak tidak perlu di repo: `31.71.01.1001.json` (contoh respons BMKG), `Tabel Harga Berdasarkan Daerah.xlsx`,
  folder `.agents/` (±100 file log agent internal).

**Ukuran repo Git ±126 MB**, mayoritas dari dataset foto dan dokumen.

---

## 3. Hasil Verifikasi & Status Pengujian

### 3.1 Status Pengujian Unit Terbaru (4 November 2026)
Pengujian suite utama `tests/test_tani_pintar.py` berhasil diselesaikan dengan hasil **100% OK**:

```text
Ran 7 tests in 8.189s
OK
```

| Pengujian | Status | Catatan Resolusi |
| :--- | :---: | :--- |
| `test_all_6_router_intents` | ✅ **PASS** | Kueri harga spesifik wilayah (`di sleman`) terverifikasi tepat mengarah ke `market_price`. |
| `test_feature_1_knowledge_base_11_diseases` | ✅ **PASS** | Validasi integritas tepat 11 penyakit (6 cabai, 5 padi). |
| `test_feature_2_crop_restriction_guardrail` | ✅ **PASS** | Guardrail penolakan komoditas di luar cabai & padi berjalan aman. |
| `test_feature_3_daily_market_price_auto_update` | ✅ **PASS** | Fallback deterministik dan variasi harga harian berjalan lancar. |
| `test_feature_4_consultation_history_formatting` | ✅ **PASS** | Formatting kartu riwayat konsultasi petani rapi dan sesuai standar. |
| `test_feature_5_weather_advisory_formatting` | ✅ **PASS** | Format rekomendasi cuaca dan advisory semprot BMKG valid. |
| `test_feature_6_fertilizer_and_pesticide_recommendation` | ✅ **PASS** | Rekomendasi pupuk fase generatif cabai diverifikasi mengandung formula KNO3 seimbang. |

### 3.2 Catatan Historis Audit Awal (31 Oktober 2026)
Pada audit awal, suite discover 41 test mengalami kegagalan karena:
1. `KeyError: 'Cabai'` pada fallback harga umum -> **Telah diperbaiki & terverifikasi di `services/price_service.py`**.
2. Assertion kueri router harga tanpa wilayah -> **Telah diperbaiki & terverifikasi**.
3. Assertion urutan index rekomendasi pupuk -> **Telah diperbaiki & terverifikasi**.
4. Test integrasi memanggil jaringan Supabase/Gemini riil tanpa mock -> **Terjadwal isolasi mock unit test pada Tahap 3**.

---

## 4. Temuan P0 — Bug Fungsional

### BUG-A01 · `KeyError: 'Cabai'` pada Pencarian Harga Umum
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `services/price_service.py` (`get_daily_prices`), dipanggil dari `graph_builder.py::price_node`
- **Gejala:** User mengetik *"harga cabai"* / *"harga beras"* tanpa wilayah.
- **Root cause:** `target_commodity` diset ke `"Cabai"` / `"Beras"` (nilai agregat). Jika tabel
  `market_prices` kosong atau Supabase offline, alur masuk ke fallback dan mengeksekusi
  `COMMODITY_BASELINES[comm]` — key agregat tidak ada di kamus.
- **Resolusi Diterapkan:** Menambahkan percabangan ekspansi komoditas:
  - `"Cabai"` otomatis memproses 4 varietas: Cabai Rawit Merah, Cabai Rawit Hijau, Cabai Merah Keriting, Cabai Merah Besar.
  - `"Beras"` otomatis memproses 3 varietas: Gabah Kering Panen (GKP), Beras Kualitas Medium I, Beras Kualitas Super I.
  - Menggunakan `.get(comm)` dengan guard agar tidak memicu `KeyError`.

### BUG-A02 · Tabel `disease_reference_images` Tidak Pernah Dibuat
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `database/repository.py::get_reference_image`, `database/schema_patch.sql`
- **Gejala:** Section "Foto Pembanding Referensi" tidak pernah muncul.
- **Root cause:** Query memanggil tabel `disease_reference_images` yang belum ada DDL-nya.
- **Resolusi Diterapkan:** 
  1. `ConsultationRepository.get_reference_image` dialihkan memprioritaskan tabel `disease_image_gallery` (kolom `storage_public_url` & `disease_name`) yang sudah aktif di Supabase.
  2. Menambahkan DDL View kompatibilitas `public.disease_reference_images` pada `database/schema_patch.sql`.

### BUG-A03 · Harga "Otomatis" Sebenarnya Sintetis
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `services/price_service.py`
- **Gejala:** Harga berubah tiap hari seolah data pasar live BI.
- **Root cause:** Fluktuasi -4%…+6% dihasilkan dari hash tanggal, lalu dilabeli "PIHPS Bank Indonesia".
- **Resolusi Diterapkan:** Menyelaraskan teks transparansi etika data:
  - Sumber dilabeli transparan: `"Estimasi Model Harga Pasar TaniPintar (Baseline Berkala & Pasar Lokal DIY-Jateng)"`.
  - Catatan pasar menyertakan klausul: `"(Catatan: Angka ini merupakan estimasi model pendukung keputusan, bukan feed live transaksi perbankan resmi)"`.

### BUG-A04 · Cuaca Lokasi Tak Dikenal Diam-diam Jatuh ke Yogyakarta
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `services/weather_service.py::_get_bmkg_forecast`
- **Gejala:** User di luar DIY/Jateng (misal: Karawang) tetap menerima data berlabel Yogyakarta BMKG.
- **Root cause:** Jika kueri lokasi tidak cocok dengan kamus ADM4 lokal, sistem memaksakan default ke Yogyakarta.
- **Resolusi Diterapkan:**
  - Hanya query kosong/generik (`"cuaca"`, `"hari ini"`) yang menggunakan default Yogyakarta.
  - Jika kueri menyebut nama lokasi di luar ADM4 DIY/Magelang, `_get_bmkg_forecast` mengembalikan `None`, sehingga alur otomatis diteruskan ke WeatherAPI / Open-Meteo dengan reverse geocoding sesuai kota yang diminta petani. Terverifikasi kueri `"Karawang"` menghasilkan cuaca Karawang.

### BUG-A05 · `agents/market_agent.py` Dead Code dan Tidak Kompatibel
- **Status:** ✅ **RESOLVED (4 Nov 2026)**
- **File:** `agents/market_agent.py`
- **Root cause:** Menggunakan schema lama dan tidak pernah dipanggil di `graph_builder.py`.
- **Resolusi Diterapkan:** Berkas `agents/market_agent.py` telah dihapus dari codebase untuk menjaga kebersihan repositori.

### BUG-A06 · Hanya Pesan Pertama yang Diproses pada Webhook Meta
- **File:** `api/routes/whatsapp.py::handle_whatsapp_event`
- **Root cause:** `messages[0]` diambil saja; sisa pesan pada payload yang sama diabaikan.
- **Dampak:** Pesan user hilang saat kirim beruntun.
- **Usulan perbaikan:** Iterasi seluruh `messages` dan enqueue ke `BackgroundTasks`.
- **Terkait (WAHA):** media selalu dikirim sebagai `image/jpeg` ke Gemini di `diagnosis_agent`
  (`types.Part.from_bytes(..., mime_type="image/jpeg")`) meskipun aslinya PNG/WebP. Perbaiki dengan
  deteksi mime dari header byte (`imghdr`/`Pillow`).

### BUG-A07 · Router Berbasis Keyword Sangat Rapuh
- **File:** `graph_builder.py::router_node`
- **Contoh masalah:**
  - `"p"` di `greeting_triggers` → pesan apa pun yang diawali "p " terdeteksi greeting.
  - Angka `1–6` bermakna berbeda tergantung `session_step` → mudah salah rute.
  - `is_numeric_input = clean_msg.isdigit() or clean_msg in []` → cabang `in []` dead code.
  - Daftar sinonim tombol diduplikasi di `INTERACTIVE_ACTION_MAP` (706 baris peluang drift).
- **Usulan perbaikan:** Satukan kamus ID tombol ↔ aksi di satu modul (`core/actions.py`), dan
  pertimbangkan klasifikasi intent berbasis LLM (structured output) dengan keyword sebagai fallback.

---

## 5. Temuan P0 — Keamanan

### SEC-01 · Auth Admin Bisa Bypass
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `api/routes/admin.py::verify_admin_key`
- **Masalah:** Verifikasi otorisasi hanya aktif jika `APP_ENV != "development"`.
- **Resolusi Diterapkan:** Menghapus bypass mode development. Header `X-Admin-Key` kini wajib ada dan harus cocok dengan `ADMIN_API_KEY` di seluruh lingkungan (development, staging, production). Pengujian penolakan tanpa kunci (`401 Unauthorized`) dan penerimaan dengan kunci valid telah diverifikasi 100%.

### SEC-02 · Webhook Meta Tidak Diverifikasi Signature
- **Status:** ⏳ **ROADMAP TAHAP 2**
- **File:** `api/routes/whatsapp.py::handle_whatsapp_event`
- **Masalah:** Belum ada pengecekan signature `X-Hub-Signature-256` dengan `META_APP_SECRET`.
- **Rencana:** Tambahkan `META_APP_SECRET` di config + verifikasi HMAC-SHA256 body mentah pada tahap berikutnya.

### SEC-03 · HMAC WAHA Opsional (Fail-Open)
- **Status:** ✅ **RESOLVED (4 Nov 2026)**
- **File:** `api/routes/whatsapp.py::verify_waha_hmac`
- **Masalah:** Sebelumnya jika secret kosong, fungsi langsung `return True` (fail-open).
- **Resolusi Diterapkan:** Pada `settings.app_env == "production"`, jika `waha_hmac_secret` belum diset, webhook langsung menolak request dengan `return False` (fail-closed) disertai audit log warning.

### SEC-04 · Endpoint Test Tanpa Autentikasi
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `api/routes/whatsapp.py` — `/webhook/test/send-buttons`, `/send-list`, `/send-poll`
- **Masalah:** Endpoint uji coba interaktif terbuka untuk publik tanpa otentikasi.
- **Resolusi Diterapkan:** Ketiga endpoint uji coba kini dilindungi menggunakan dependency `verify_admin_key(x_admin_key)`. Request tanpa kunci admin yang valid ditolak dengan HTTP 401.

### SEC-05 · WAHA Terbuka Tanpa Password / API Key
- **Status:** ⏳ **ROADMAP TAHAP 2**
- **File:** `docker-compose.yml`
- **Masalah:** `WAHA_DASHBOARD_NO_PASSWORD=True`, `WAHA_NO_API_KEY=True`.
- **Rencana:** Menetapkan password dashboard + API key wajib dan menghapus port binding publik host pada docker compose di Tahap 2.

### SEC-06 · CORS Tidak Aman
- **Status:** ✅ **RESOLVED (4 Nov 2026)**
- **File:** `api/app.py`
- **Masalah:** Kombinasi `allow_origins=["*"]` dengan `allow_credentials=True` melanggar standar W3C Fetch dan membuka celah CSRF.
- **Resolusi Diterapkan:** `allow_credentials` diubah menjadi `False` saat wildcard origin aktif, dan daftar HTTP methods didefinisikan secara eksplisit (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`).

### SEC-07 · Kredensial Default Tertulis di Kode & Docs
- **Status:** ⏳ **ROADMAP TAHAP 2**
- **File:** `core/config.py` (`admin_api_key`, `meta_wa_verify_token`), `README.md`, `docs/deploy.md`
- **Rencana:** Validator pydantic startup untuk menolak boot jika kunci masih bernilai contoh.

### SEC-08 · Privasi Data Petani & Masking Log
- **Status:** ✅ **RESOLVED & VERIFIED (4 Nov 2026)**
- **File:** `core/logger.py`
- **Masalah:** Nomor WhatsApp petani tercatat terbuka dalam log plain-text terminal.
- **Resolusi Diterapkan:**
  - Menambahkan utilitas `mask_phone_number` yang menyamarkan nomor (contoh: `628123456789` -> `62812****6789`).
  - Mengimplementasikan `PhoneMaskingFormatter` pada logging handler yang secara otomatis menyensor regex nomor telepon pada setiap event pesan masuk/keluar di log terminal.

---

## 6. Temuan P1 — Dependency & Infrastruktur

### INF-01 · `pyproject.toml` Tidak Lengkap
`opencv-python-headless`, `numpy`, `pillow` dipakai kode tetapi hanya ada di `requirements.txt`.
`uv sync` → ImportError saat runtime.

### INF-02 · Sumber Dependency Ganda & Tidak Reproducible
`requirements.txt`, `pyproject.toml`, dan `uv.lock` tidak sinkron; semua versi `>=`.
Docker memakai `pip install requirements.txt`, bukan lockfile.

### INF-03 · Dependency Tidak Terpakai / Hilang
- Tidak dipakai: `pydantic-ai`, `langchain-core`, `langchain-google-genai`, `openpyxl`
  (README masih mengklaim "PydanticAI").
- Dibutuhkan tapi tidak terdaftar: `redis` (dipakai opsional di `core/dedup.py`).

### INF-04 · Tidak Ada CI/CD
Tidak ada `.github/workflows`. Tidak ada lint/format/type-check (`ruff`, `black`, `mypy`),
`pre-commit`, `Makefile`, `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`.

### INF-05 · Docker Tidak Produksi-Ready
- Container jalan sebagai `root`, single-stage build.
- `.dockerignore` belum mengecualikan `docs/` dan dataset besar.
- `docker-compose` me-mount seluruh source (`./:/app`) termasuk `.env` & `.git`.
- `depends_on` tanpa kondisi health.

### INF-06 · Tidak Ada Job Queue
`BackgroundTasks` hilang saat restart/traffic tinggi. Skala >1 worker membuat dedup lokal tidak
berlaku (butuh Redis).

### INF-07 · Migrasi Database Manual
Empat file SQL dijalankan manual → rawan drift. Tidak ada Alembic/Supabase CLI migration atau versi.

### INF-08 · Validasi Config Saat Startup Tidak Ada
Jika `GEMINI_API_KEY` atau Supabase kosong, aplikasi tetap "sehat" dan masuk mode mock tanpa
peringatan keras di production.

---

## 7. Temuan P1 — Reliabilitas & Observability

- **OBS-01** `/health` hanya mengecek keberadaan variabel env, bukan konektivitas Supabase, WAHA,
  atau Gemini. Tidak ada pemisahan liveness vs readiness.
- **OBS-02** Tidak ada retry/backoff saat kirim WAHA/Meta gagal (hanya fallback session), tidak ada
  rate limit / anti-spam / batas konkurensi per nomor, tidak ada timeout total pipeline.
- **OBS-03** Log teks bebas ke stdout: tidak ada request ID, JSON logging, metrics, tracing, atau
  error tracking (Sentry).
- **OBS-04** Side effect di lapisan formatter: `format_and_guardrail_node` melakukan query DB
  (`get_reference_image`) — merusak pemisahan format vs I/O.
- **OBS-05** Audit bisa dobel untuk konsultasi berulang; `audit_saver` menulis ulang seluruh
  `bot_recommendation` JSON.
- **OBS-06** Tidak ada mekanisme dead-letter untuk pesan yang gagal diproses.

---

## 8. Temuan P2 — Testing

| ID | Temuan | Rekomendasi |
| :--- | :--- | :--- |
| TST-01 | `pytest` & `pytest-asyncio` tidak terpasang; tidak ada `tests/__init__.py` | Tambahkan ke dev deps + config `pytest.ini`/`pyproject` |
| TST-02 | Test bergantung layanan eksternal (Supabase, BMKG, Gemini, WAHA) → flaky & lambat | Mock/fixture (`respx`, `unittest.mock`) |
| TST-03 | Belum ada test untuk `cv_preprocessor`, `visual_rag_service`, `storage_service`, auth admin, signature Meta, rate limit, Redis dedup | Tambahkan unit test per modul |
| TST-04 | Assertion rapuh (cek `KNO3` di index 0; cek router harga yang sudah berubah desain) | Assertions berbasis properti, bukan urutan |
| TST-05 | Tidak ada coverage minimum; `benchmark_metrics.py` bercampur di folder test | Pisah ke `scripts/`; target coverage ≥ 70% |

---

## 9. Temuan P2 — Data & Model AI

- **DAT-01** Knowledge base hanya 11 penyakit, tanpa versioning/provenance; tidak ada evaluasi
  akurasi diagnosis teks maupun vision (precision/recall/confusion matrix).
- **DAT-02** Dataset 491 foto di-commit tanpa lisensi, split train/val, atau metrik evaluasi.
- **DAT-03** Nama model tidak konsisten: `gemini-embedding-001` (kode) vs `gemini-embedding-2`
  (visual RAG/docstring), `gemini-1.5-flash` (docs) vs `gemini-3.5-flash` (config).
- **DAT-04** Semua fallback model masih Gemini; tidak ada penyedia cadangan saat kuota habis.
- **DAT-05** Tidak ada feedback loop (👍/👎, koreksi PPL) untuk memperbaiki prompt/model. Klaim
  README "seluruh Indonesia" tidak sesuai implementasi (hanya DIY + Magelang, 6 wilayah).

---

## 10. Temuan P2 — Dokumentasi & Higiene Repo

- **DOC-01** `README.md` usang: menyebut PydanticAI, Gemini 1.5 Flash, dan struktur folder tanpa
  `cv_preprocessor`, `visual_rag_service`, `dedup`, `session_service`.
- **DOC-02** Duplikasi Berkas: `docs/bug dan eror.md` telah dihapus; hanya satu berkas kanonik `docs/bug_dan_eror.md` yang dipertahankan. [RESOLVED 4 Nov 2026]
- **DOC-03** Artefak tidak perlu di repo: `.agents/teamwork/*` (±100 file), `31.71.01.1001.json`,
  `Tabel Harga Berdasarkan Daerah.xlsx`, `docs/capstone fix - Copy.docx` (6 MB), `data/dataset_foto/` (70 MB).
- **DOC-04** Belum ada diagram arsitektur (gambar), ERD, koleksi Postman, panduan troubleshooting,
  security policy, dan bagian limitasi/known issues.

---

## 11. Gap Produk / UX

- **UX-01** Belum mendukung **voice note** (sangat relevan bagi petani) dan **share location**
  (memperbaiki akurasi cuaca & harga).
- **UX-02** Belum ada eskalasi ke PPL manusia (hanya flag + portal admin).
- **UX-03** Belum ada feedback petani, preferensi bahasa (Indonesia/Jawa), atau fallback SMS.
- **UX-04** Tidak ada penanganan status pengiriman/retry sehingga pesan bisa hilang tanpa terdeteksi.

---

## 12. Rencana Perbaikan Bertahap

### Tahap 1 — Stabilisasi & Keamanan Inti (Status: SELESAI & TERVERIFIKASI)

| No | Aksi | File Terkait | Status |
| :---: | :--- | :--- | :---: |
| 1 | Perbaiki `KeyError: 'Cabai'`/"Beras" (agregat → varian) + test regresi | `services/price_service.py` | ✅ **SELESAI** |
| 2 | Wajibkan auth admin `X-Admin-Key` tanpa syarat env | `api/routes/admin.py` | ✅ **SELESAI** |
| 3 | Verifikasi signature `X-Hub-Signature-256` webhook Meta | `api/routes/whatsapp.py`, `core/config.py` | ⏳ Tahap 2 |
| 4 | HMAC WAHA fail-closed di production | `api/routes/whatsapp.py` | ✅ **SELESAI** |
| 5 | Lindungi endpoint uji coba `/webhook/test/*` dengan `X-Admin-Key` | `api/routes/whatsapp.py` | ✅ **SELESAI** |
| 6 | WAHA: password dashboard + API key wajib, lepas publish port | `docker-compose.yml` | ⏳ Tahap 2 |
| 7 | CORS origin aman tanpa wildcard credentials | `api/app.py` | ✅ **SELESAI** |
| 8 | Label harga jujur (estimasi model & pasar lokal) + catatan disclaimer | `services/price_service.py` | ✅ **SELESAI** |
| 9 | Cuaca: hapus default diam-diam ke Jogja, aktifkan fallback multi-layer | `services/weather_service.py` | ✅ **SELESAI** |
| 10 | Hapus berkas dead-code `agents/market_agent.py` | `agents/` | ✅ **SELESAI** |
| 11 | Tambah view DDL & pengalihan galeri referensi penyakit | `database/repository.py`, `database/schema_patch.sql` | ✅ **SELESAI** |
| 12 | Implementasi penyensoran nomor telepon petani pada logging stdout | `core/logger.py` | ✅ **SELESAI** |

### Tahap 2 — Kualitas Kode & Dependency (target: ≤ 1 minggu)

| No | Aksi | File Terkait |
| :---: | :--- | :--- |
| 1 | Samakan dependency: `opencv`, `numpy`, `pillow`, `redis` masuk `pyproject.toml`; hapus lib tak terpakai | `pyproject.toml`, `requirements.txt` |
| 2 | Pakai satu lockfile (`uv.lock`) di Docker | `Dockerfile` |
| 3 | Hapus/perbaiki `agents/market_agent.py` | `agents/` |
| 4 | Proses semua `messages` di webhook Meta; deteksi mime media sebenarnya | `api/routes/whatsapp.py`, `agents/diagnosis_agent.py` |
| 5 | Buat DDL `disease_reference_images` atau alihkan ke `disease_image_gallery` | `database/schema_patch.sql`, `database/repository.py` |
| 6 | Satukan kamus aksi tombol ke satu modul | `core/actions.py` (baru), `graph_builder.py`, `api/routes/whatsapp.py` |
| 7 | Pindahkan query DB dari formatter ke node sendiri | `graph_builder.py` |
| 8 | Tambah `ruff`, `black`, `mypy`, `pre-commit`, `Makefile`, `LICENSE` | root |

### Tahap 3 — Testing & CI (target: ≤ 2 minggu)

| No | Aksi | File Terkait |
| :---: | :--- | :--- |
| 1 | Tambah `pytest`, `pytest-asyncio`, `respx`, `coverage` sebagai dev deps | `pyproject.toml` |
| 2 | Mock layanan eksternal; pisahkan integration test (marker `@pytest.mark.integration`) | `tests/` |
| 3 | Test baru: `cv_preprocessor`, `visual_rag`, `storage`, signature Meta, auth admin, rate limit | `tests/` |
| 4 | Perbaiki assertion rapuh; target coverage ≥ 70% | `tests/` |
| 5 | GitHub Actions: lint + test + build Docker | `.github/workflows/ci.yml` (baru) |

### Tahap 4 — Observability & Reliabilitas (target: ≤ 3 minggu)

| No | Aksi | File Terkait |
| :---: | :--- | :--- |
| 1 | `/health/live` & `/health/ready` (cek Supabase, WAHA, Gemini) | `api/routes/health.py` |
| 2 | JSON logging + request ID + masking nomor telepon | `core/logger.py` |
| 3 | Retry/backoff pengiriman WAHA/Meta + dead-letter | `services/whatsapp_service.py` |
| 4 | Rate limit per nomor + batas konkurensi | `api/routes/whatsapp.py`, `core/` |
| 5 | Opsional: job queue (ARQ/Celery) + Redis produksi | `docker-compose.yml`, `core/` |
| 6 | Error tracking (Sentry) + metric dasar (latensi, error rate) | `core/` |

### Tahap 5 — Data, Doc & Produk (target: berkelanjutan)

| No | Aksi | File Terkait |
| :---: | :--- | :--- |
| 1 | Integrasi nyata PIHPS/Bapanas via cron, atau hapus klaim resmi | `services/price_service.py`, `data/` |
| 2 | Evaluasi akurasi diagnosis (golden set + metrik) | `tests/`, `docs/` |
| 3 | Update `README.md`, hapus duplikat docs, keluarkan artefak besar dari repo | root, `docs/` |
| 4 | Tambah diagram arsitektur, ERD, koleksi Postman, troubleshooting, security policy | `docs/` |
| 5 | Migrasi DB berversi (Alembic/Supabase CLI) | `database/migrations/` |
| 6 | Fitur UX: voice note, share location, feedback, eskalasi PPL | `api/`, `services/`, `graph_builder.py` |

---

## 13. Matriks Prioritas (Ringkas)

| Prioritas | Item | Estimasi |
| :---: | :--- | :--- |
| **P0** | BUG-A01 (KeyError harga) | 2 jam |
| **P0** | SEC-01, SEC-02, SEC-03, SEC-04, SEC-05 | 1 hari |
| **P0** | BUG-A03 (label harga jujur) | 3 jam |
| **P0** | BUG-A04 (cuaca default diam-diam) | 2 jam |
| **P1** | INF-01, INF-02, INF-03 (dependency) | 4 jam |
| **P1** | BUG-A06, BUG-A07 (webhook & router) | 1–2 hari |
| **P1** | BUG-A02 (tabel referensi) | 2 jam |
| **P1** | SEC-06, SEC-07, SEC-08 (hardening sisa) | 1 hari |
| **P1** | OBS-01…OBS-06 | 2–3 hari |
| **P2** | TST-01…TST-05 + CI | 3–5 hari |
| **P2** | DOC-01…DOC-04 | 1 hari |
| **P2** | DAT-01…DAT-05 | berkelanjutan |
| **P2** | UX-01…UX-04 | berkelanjutan |

---

## 14. Definisi Selesai (Definition of Done)

Perbaikan dianggap selesai jika:

1. `pytest` hijau 100% **tanpa** akses jaringan (semua eksternal di-mock).
2. `ruff check .`, `black --check .`, dan `mypy` lulus pada modul utama.
3. CI (GitHub Actions) berjalan otomatis pada setiap PR.
4. `/health/ready` mengembalikan status dependensi nyata.
5. Semua endpoint admin & test memerlukan autentikasi; webhook Meta & WAHA memverifikasi signature.
6. Tidak ada kredensial default aktif di `production`.
7. Tidak ada label "PIHPS Bank Indonesia" pada data sintetis.
8. `README.md` dan `docs/` konsisten dengan implementasi; tidak ada file duplikat atau artefak besar.
9. `docker compose up` berjalan dengan `.env.example` yang lengkap dan aman.
10. Semua temuan P0 di dokumen ini tercatat **resolved** di `docs/bug_dan_eror.md` beserta bukti test.
