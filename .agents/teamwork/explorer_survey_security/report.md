# 🛡️ Laporan Audit Keamanan & Sanitasi Kredensial: `laporan.md`
**TaniPintar Bot Project — Security & Credential Sanitization Survey**  
*Auditor: Explorer Survey & Security Agent*  
*Tanggal: 2026-10-01*

---

## 📌 1. Ringkasan Eksekutif (Executive Summary)

Berdasarkan penugasan pada `task.md` dan `ORIGINAL_REQUEST.md` (khususnya R1: *Kredensial & Sanitasi Keamanan Dokumen*), telah dilakukan audit menyeluruh terhadap dokumen teknis `laporan.md` serta verifikasi silang terhadap berkas konfigurasi sistem (`core/config.py`, `.env`, `.env.example`, dan `deploy.md`).

### Temuan Utama:
1. **Kebocoran Kunci API Produksi (Kritis / High)**: Ditemukan API Key aktif WeatherAPI.com (`76d7a4136a6948e8ac464008250810`) yang tercetak secara terbuka (*plaintext*) pada tiga (3) lokasi berbeda dalam `laporan.md`:
   - Diagram alur arsitektur Mermaid (Baris 90)
   - Tabel spesifikasi kredensial (Baris 241)
   - Narasi deskripsi fitur layanan cuaca (Baris 317)
2. **Eksposur Nomor WhatsApp Aktif (Sedang / Medium)**: Nomor WhatsApp bot produksi (`62895418133345`) tercantum secara eksplisit pada Baris 16 tanpa penyamaran (*masking*).
3. **Eksposur Path Lokal Filesystem & Tautan `.env` Langsung (Sedang / Medium)**: Terdapat URI absolut lokal `file:///e:/wa%20bot%20longchain/...` pada Baris 211, 233, dan 269, termasuk hyperlink langsung ke berkas `.env` lokal yang memuat kredensial riil.
4. **Kesenjangan Konfigurasi `.env.example`**: Variabel `WEATHER_API_KEY` dan `ADMIN_API_KEY` tidak tercantum dalam `.env.example`, berpotensi menyebabkan kegagalan deployment atau fallback otomatis ke default credential yang lemah (`tanipintar_admin_secret_2026`).

---

## 🔍 2. Katalog Temuan Kredensial & Data Sensitif di `laporan.md`

Berikut adalah rincian lengkap setiap temuan pada `laporan.md`:

| No | Lokasi (Baris) | Kategori | Konten Saat Ini (Verbatim) | Tingkat Risiko | Rekomendasi Remediasi |
|---|---|---|---|---|---|
| **SEC-01** | Baris 90 | Diagram Mermaid Arsitektur | `WeatherSvc <-->\|API Key: 76d7a4136a6948e8ac464008250810\| WeatherAPI` | **High / Critical** | Ganti dengan referensi variabel lingkungan: `WeatherSvc <-->\|WEATHER_API_KEY (.env)\| WeatherAPI` |
| **SEC-02** | Baris 241 | Tabel 4.4 Kredensial | `\| \`WEATHER_API_KEY\` \| [WeatherAPI.com](https://www.weatherapi.com/) \| API Key cuaca (Aktif: \`76d7a4136a6948e8ac464008250810\`). \|` | **High / Critical** | Hapus plaintext key, ganti dengan rujukan aman: `\| \`WEATHER_API_KEY\` \| [WeatherAPI.com](https://www.weatherapi.com/) \| API Key layanan cuaca (diambil dari variabel lingkungan \`.env\` / \`<WEATHER_API_KEY>\`). \|` |
| **SEC-03** | Baris 317 | Paragraf Fitur 5.4 Cuaca | `- **Engine Cuaca**: Menggunakan **WeatherAPI.com** (Key: \`76d7a4136a6948e8ac464008250810\`) dengan geocoding otomatis...` | **High / Critical** | Hapus key, ubah kalimat: `- **Engine Cuaca**: Menggunakan **WeatherAPI.com** (terotentikasi via \`WEATHER_API_KEY\` pada \`.env\`) dengan geocoding otomatis...` |
| **SEC-04** | Baris 16 | Ringkasan Eksekutif 1.1 | `- **Konektivitas WhatsApp**: Berjalan secara live menggunakan WAHA engine \`WEBJS\` terhubung ke nomor bot WhatsApp aktif (\`62895418133345\`).` | **Medium** | Lakukan masking nomor aktif: `- **Konektivitas WhatsApp**: Berjalan secara live menggunakan WAHA engine \`WEBJS\` terhubung ke nomor bot WhatsApp aktif (\`+62 895-4181-XXXX\` / terdaftar pada sesi WAHA).` |
| **SEC-05** | Baris 211, 233, 269 | URI Absolut Lokal | Hyperlink format `file:///e:/wa%20bot%20longchain/...` menuju `requirements.txt`, `pyproject.toml`, `.env`, dan `database/schema.sql`. | **Medium** | Ubah menjadi inline backticks atau relative links murni tanpa protokol `file:///` dan drive lokal `e:/`. |
| **SEC-06** | Baris 245 & 341 | Proteksi Admin API | Penggunaan header `X-Admin-Key` tanpa panduan pergantian default secret di produksi. | **Low / Informational** | Tambahkan panduan wajib menimpa default secret `tanipintar_admin_secret_2026` via environment variable `ADMIN_API_KEY`. |

---

## 📊 3. Matriks Komparasi Konfigurasi Sistem (Cross-Reference Matrix)

Tabel berikut menunjukkan keselarasan variabel lingkungan antara kode sumber (`core/config.py`), template publik (`.env.example`), berkas lingkungan aktif (`.env`), dan dokumen teknis (`laporan.md`):

| Variabel Lingkungan | Ada di `core/config.py`? | Ada di `.env.example`? | Ada di `.env`? | Tercatat di `laporan.md`? | Nilai Bawaan (*Default*) di Kode | Status Keamanan & Catatan |
|---|:---:|:---:|:---:|:---:|---|---|
| `APP_ENV` | ✅ | ✅ | ✅ | ❌ | `"development"` | Mengontrol bypass otentikasi di `api/routes/admin.py`. |
| `APP_HOST` | ✅ | ✅ | ✅ | ❌ | `"0.0.0.0"` | Host bind server. |
| `APP_PORT` | ✅ | ✅ | ✅ | Di Bab 4.5 | `8000` | Port listen server FastAPI. |
| `LOG_LEVEL` | ✅ | ✅ | ✅ | ❌ | `"INFO"` | Level logging. |
| `GEMINI_API_KEY` | ✅ | ✅ | ✅ | ✅ | `""` | Kunci akses Gemini API. Aman (tidak bocor di `laporan.md`). |
| `GEMINI_MODEL` | ✅ | ✅ | ✅ | Di Bab 3.1 | `"gemini-3.5-flash"` | `.env.example` masih mencatat `gemini-1.5-flash` (perlu penyelarasan). |
| `EMBEDDING_MODEL`| ✅ | ✅ | ✅ | Di Bab 3.1 | `"gemini-embedding-001"` | `.env.example` mencatat `models/text-embedding-004` (perlu penyelarasan). |
| `SUPABASE_URL` | ✅ | ✅ | ✅ | ✅ | `""` | URL Supabase project. Aman (placeholder di `laporan.md`). |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | ✅ | ✅ | ✅ | `""` | Kunci rahasia bypass RLS. Aman (format contoh di `laporan.md`). |
| `SUPABASE_BUCKET_NAME` | ✅ | ✅ | ✅ | ✅ | `"crop-symptoms"` | Nama bucket foto keluhan. |
| `META_WA_PHONE_NUMBER_ID` | ✅ | ✅ | ✅ | ✅ | `""` | ID nomor Meta. Aman. |
| `META_WA_ACCESS_TOKEN` | ✅ | ✅ | ✅ | ✅ | `""` | Token Meta Graph API. Aman. |
| `META_WA_VERIFY_TOKEN` | ✅ | ✅ | ✅ | ✅ | `"tanipintar_webhook_verify_token_secret"` | Token verifikasi webhook Meta. |
| `META_GRAPH_VERSION` | ✅ | ✅ | ✅ | Di Bab 3.1 | `"v20.0"` | Versi Meta Graph API. |
| `WHATSAPP_PROVIDER` | ✅ | ✅ | ✅ | ✅ | `"waha"` | Provider aktif (`waha` / `meta`). |
| `WAHA_BASE_URL` | ✅ | ✅ | ✅ | ✅ | `"http://localhost:3000"` | Endpoint WAHA internal/eksternal. |
| `WAHA_SESSION` | ✅ | ✅ | ✅ | ✅ | `"default"` | Sesi WAHA aktif. |
| `CONFIDENCE_THRESHOLD` | ✅ | ✅ | ✅ | ✅ | `0.70` | Ambang batas kepastian guardrail. |
| **`ADMIN_API_KEY`** | ✅ (baris 37) | ❌ **HILANG** | ❌ **HILANG** | ✅ (baris 245) | `"tanipintar_admin_secret_2026"` | **GAP**: Tidak ada di `.env.example` maupun `.env`. Menggunakan default hardcoded. |
| **`WEATHER_API_KEY`** | ✅ (baris 40) | ❌ **HILANG** | ✅ (baris 32) | ✅ (baris 241) | `""` | **GAP & LEAK**: Tidak ada di `.env.example`, namun tercetak plaintext di `laporan.md`. |

---

## 🛠️ 4. Rencana Tindakan Remediasi Terperinci (Detailed Remediation Plan)

Berikut adalah usulan perubahan teks *Before vs After* yang siap diterapkan oleh Editor / Implementer pada berkas `laporan.md`:

### 4.1 Remediasi SEC-04: Masking Nomor Telepon Bot (Baris 16)
```markdown
<<< BEFORE (Baris 16)
- **Konektivitas WhatsApp**: Berjalan secara live menggunakan WAHA engine `WEBJS` terhubung ke nomor bot WhatsApp aktif (`62895418133345`).
=== AFTER
- **Konektivitas WhatsApp**: Berjalan secara live menggunakan WAHA engine `WEBJS` terhubung ke nomor bot WhatsApp operasional (`+62 895-4181-XXXX` / terdaftar pada sesi WAHA).
>>>
```

### 4.2 Remediasi SEC-01: Diagram Alur Arsitektur Mermaid (Baris 90)
```markdown
<<< BEFORE (Baris 90)
    WeatherSvc <-->|API Key: 76d7a4136a6948e8ac464008250810| WeatherAPI
=== AFTER
    WeatherSvc <-->|WEATHER_API_KEY (.env)| WeatherAPI
>>>
```

### 4.3 Remediasi SEC-05: Sanitasi URI Absolut Lokal (Baris 211, 233, 269)
```markdown
<<< BEFORE (Baris 211)
Seluruh paket Python berikut didefinisikan dalam [`requirements.txt`](file:///e:/wa%20bot%20longchain/requirements.txt) dan [`pyproject.toml`](file:///e:/wa%20bot%20longchain/pyproject.toml):
=== AFTER
Seluruh paket Python berikut didefinisikan dalam `requirements.txt` dan `pyproject.toml`:
>>>
```

```markdown
<<< BEFORE (Baris 233)
Aplikasi membutuhkan kredensial pihak ketiga yang harus didefinisikan pada berkas [`.env`](file:///e:/wa%20bot%20longchain/.env):
=== AFTER
Aplikasi membutuhkan kredensial pihak ketiga yang harus didefinisikan pada berkas `.env` (disalin dari template aman `.env.example`):
>>>
```

```markdown
<<< BEFORE (Baris 269)
2. **Jalankan Skrip DDL**: Eksekusi seluruh isi berkas [`database/schema.sql`](file:///e:/wa%20bot%20longchain/database/schema.sql) untuk membentuk tabel `knowledge_base`, `disease_reference_images`, `consultation_audits`, `chat_sessions`, `market_prices`, dan fungsi RPC `match_knowledge`.
=== AFTER
2. **Jalankan Skrip DDL**: Eksekusi seluruh isi berkas `database/schema.sql` untuk membentuk tabel `knowledge_base`, `disease_reference_images`, `consultation_audits`, `chat_sessions`, `market_prices`, dan fungsi RPC `match_knowledge`.
>>>
```

### 4.4 Remediasi SEC-02: Tabel Kredensial 4.4 (Baris 241 & 245)
```markdown
<<< BEFORE (Baris 241-245)
| `WEATHER_API_KEY` | [WeatherAPI.com](https://www.weatherapi.com/) | API Key cuaca (Aktif: `76d7a4136a6948e8ac464008250810`). |
| `WHATSAPP_PROVIDER` | Internal Config | Menentukan provider aktif: `waha` atau `meta` (default: `waha`). |
| `WAHA_BASE_URL` | Docker Bridge Network | URL endpoint WAHA (contoh: `http://localhost:3000` di lokal, atau `http://waha:3000` di Docker). |
| `WAHA_SESSION` | WAHA Dashboard | Nama sesi WhatsApp yang digunakan (default: `chatbot` atau `default`). |
| `ADMIN_API_KEY` | Internal Config | Kunci otentikasi header `X-Admin-Key` untuk portal admin & PPL. |
=== AFTER
| `WEATHER_API_KEY` | [WeatherAPI.com](https://www.weatherapi.com/) | API Key layanan cuaca (diambil dari variabel lingkungan `.env` / `<WEATHER_API_KEY>`). |
| `WHATSAPP_PROVIDER` | Internal Config | Menentukan provider aktif: `waha` atau `meta` (default: `waha`). |
| `WAHA_BASE_URL` | Docker Bridge Network | URL endpoint WAHA (contoh: `http://localhost:3000` di lokal, atau `http://waha:3000` di Docker). |
| `WAHA_SESSION` | WAHA Dashboard | Nama sesi WhatsApp yang digunakan (default: `chatbot` atau `default`). |
| `ADMIN_API_KEY` | Internal Config | Kunci otentikasi header `X-Admin-Key` untuk portal admin & PPL (wajib diganti dengan string acak aman di `.env`). |
>>>
```

### 4.5 Remediasi SEC-03: Narasi Fitur 5.4 Prakiraan Cuaca (Baris 317)
```markdown
<<< BEFORE (Baris 317)
- **Engine Cuaca**: Menggunakan **WeatherAPI.com** (Key: `76d7a4136a6948e8ac464008250810`) dengan geocoding otomatis kota/kabupaten di Indonesia dan parameter bahasa Indonesia.
=== AFTER
- **Engine Cuaca**: Menggunakan **WeatherAPI.com** (terotentikasi via `WEATHER_API_KEY` pada berkas `.env`) dengan geocoding otomatis kota/kabupaten di Indonesia dan parameter bahasa Indonesia.
>>>
```

### 4.6 Peningkatan Format: Callout Peringatan Keamanan Variabel Lingkungan
Untuk memenuhi Acceptance Criteria Keamanan Dokumen (*"Panduan variabel lingkungan menginstruksikan pembaca untuk menggunakan konfigurasi aman melalui .env"*), tambahkan callout box pada Bagian 4.4:

```markdown
> [!IMPORTANT]
> **Praktik Terbaik Pengelolaan Kredensial & Berkas `.env`**:
> 1. Salin berkas template `.env.example` ke `.env` sebelum menjalankan bot: `cp .env.example .env`.
> 2. Jangan pernah melakukan komit (*git commit*) berkas `.env` yang berisi token produksi ke repository publik. Pastikan `.env` tercantum di `.gitignore`.
> 3. Jangan mencetak token rahasia secara terbuka di dokumen dokumentasi, diagram, atau log sistem.
> 4. Pada lingkungan produksi, gantilah kunci bawaan `ADMIN_API_KEY` dan `META_WA_VERIFY_TOKEN` dengan string acak kriptografis yang kuat.
```

---

## 🔒 5. Rekomendasi Tindak Lanjut Keamanan Operasional

1. **Rotasi Kunci WeatherAPI**: Kunci `76d7a4136a6948e8ac464008250810` telah terpapar dalam dokumen laporan dan riwayat git. Pengembang disarankan segera melakukan *Regenerate Key* di dashboard [WeatherAPI.com](https://www.weatherapi.com/) dan memperbarui nilai pada berkas `.env` lokal/server.
2. **Sinkronisasi `.env.example`**: Tambahkan baris berikut ke `.env.example` agar pengembang baru tidak mengalami missing configuration:
   ```env
   # Weather API (WeatherAPI.com)
   WEATHER_API_KEY=your_weatherapi_key_here

   # Admin Portal Authentication
   ADMIN_API_KEY=your_secure_admin_api_key_here
   ```
3. **Penyelarasan Model AI**:
   - Di `.env.example`, selaraskan model Gemini dengan kode riil (`GEMINI_MODEL=gemini-3.5-flash`, `EMBEDDING_MODEL=gemini-embedding-001`).

---
*Laporan audit ini disusun sebagai dokumen investigasi read-only. Implementasi perubahan pada `laporan.md` dapat dieksekusi oleh Editor sesuai rincian Before/After di atas.*
