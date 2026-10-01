# 🚀 Panduan Lengkap Deployment: TaniPintar Bot

Dokumen ini menjelaskan prosedur langkah-demi-langkah untuk mendeploy **TaniPintar Bot (WhatsApp AI Support Agent)** dari tahap persiapan basis data Supabase, konfigurasi kredensial, hingga *production deployment* di server dan pendaftaran Webhook WhatsApp Meta.

---

## 📑 Daftar Isi
1. [Prasyarat Sistem & Layanan](#1-prasyarat-sistem--layanan)
2. [Langkah 1: Setup Supabase Database & Storage](#langkah-1-setup-supabase-database--storage)
3. [Langkah 2: Konfigurasi Environment Variable (.env)](#langkah-2-konfigurasi-environment-variable-env)
4. [Langkah 3: Ingestion Knowledge Base ke pgvector](#langkah-3-ingestion-knowledge-base-ke-pgvector)
5. [Langkah 4: Pilihan Metode Deployment Server](#langkah-4-pilihan-metode-deployment-server)
   - [Opsi A: Docker & Docker Compose (Direkomendasikan)](#opsi-a-docker--docker-compose-direkomendasikan)
   - [Opsi B: VPS Linux (Ubuntu/Debian dengan Systemd & Nginx SSL)](#opsi-b-vps-linux-ubuntudebian-dengan-systemd--nginx-ssl)
   - [Opsi C: Cloud PaaS (Railway / Render / Google Cloud Run)](#opsi-c-cloud-paas-railway--render--google-cloud-run)
   - [Opsi D: Testing / Pengembangan Lokal dengan Ngrok](#opsi-d-testing--pengembangan-lokal-dengan-ngrok)
6. [Langkah 5: Pendaftaran Webhook di Meta WhatsApp Dashboard](#langkah-5-pendaftaran-webhook-di-meta-whatsapp-dashboard)
7. [Langkah 6: Verifikasi & Monitoring Operasional](#langkah-6-verifikasi--monitoring-operasional)

---

## 1. Prasyarat Sistem & Layanan

Sebelum memulai, pastikan Anda telah menyiapkan:
1. **Google AI Studio API Key**: Dapatkan `GEMINI_API_KEY` dari [Google AI Studio](https://aistudio.google.com/).
2. **Akun Supabase**: Buat proyek baru di [Supabase Dashboard](https://supabase.com/).
3. **Akun Meta for Developers**:
   - Daftarkan aplikasi di [Meta for Developers](https://developers.facebook.com/).
   - Aktifkan produk **WhatsApp** dan dapatkan *Phone Number ID* serta *Permanent/System User Access Token*.
4. **Server / VPS**: Server Linux dengan IP publik atau domain ber-SSL (HTTPS) untuk webhook.

---

## Langkah 1: Setup Supabase Database & Storage

### A. Eksekusi Skrip DDL Database
1. Masuk ke dashboard proyek Supabase Anda.
2. Buka menu **SQL Editor** di panel kiri.
3. Buka file [`database/schema.sql`](database/schema.sql) dari repositori ini, salin seluruh kodenya, lalu tempelkan ke SQL Editor Supabase.
4. Klik **Run**. Skrip ini akan secara otomatis:
   - Mengaktifkan ekstensi `vector`.
   - Membuat tabel `knowledge_base` lengkap dengan indeks `IVFFlat`.
   - Membuat fungsi RPC `match_knowledge` untuk pencarian semantik kemiripan kosinus.
   - Membuat tabel `chat_sessions`, `consultation_audits`, dan `market_prices`.

### B. Buat Bucket Storage untuk Foto Gejala
1. Buka menu **Storage** di dashboard Supabase.
2. Klik tombol **New bucket**.
3. Beri nama bucket: `crop-symptoms`.
4. Centang opsi **Public bucket** agar URL foto gejala dapat diakses saat audit rujukan PPL.
5. Simpan pengaturan.

---

## Langkah 2: Konfigurasi Environment Variable (`.env`)

1. Di server atau mesin lokal, salin template `.env.example` menjadi `.env`:
   ```bash
   cp .env.example .env
   ```
2. Isi nilai variabel sesuai kredensial Anda:
   ```env
   # Server Environment
   APP_ENV=production
   APP_HOST=0.0.0.0
   APP_PORT=8000
   LOG_LEVEL=INFO

   # Google Gemini AI
   GEMINI_API_KEY=AIzaSy...IsiDenganApiKeyGoogleGeminiAnda
   GEMINI_MODEL=gemini-1.5-flash
   EMBEDDING_MODEL=models/text-embedding-004

   # Supabase Credentials
   SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJh...IsiDenganServiceRoleKeyBukanAnonKey
   SUPABASE_BUCKET_NAME=crop-symptoms

   # Meta WhatsApp Cloud API
   META_WA_PHONE_NUMBER_ID=123456789012345
   META_WA_ACCESS_TOKEN=EAAG...IsiDenganAccessTokenMetaWhatsApp
   META_WA_VERIFY_TOKEN=tanipintar_webhook_verify_token_secret
   META_GRAPH_VERSION=v20.0

   # Guardrails & Admin
   CONFIDENCE_THRESHOLD=0.70
   ADMIN_API_KEY=tanipintar_admin_secret_2026
   ```

> ⚠️ **Catatan Penting**: Gunakan **Service Role Key** Supabase (bukan Anon Key) agar backend memiliki otorisasi penuh untuk insert/update data audit dan storage tanpa batasan RLS publik.

---

## Langkah 3: Ingestion Knowledge Base ke pgvector

Setelah database dibuat dan `.env` terisi, lakukan injeksi dataset 11 penyakit cabai dan padi ke Supabase:

```bash
# Menggunakan virtualenv Python
python data/ingest_knowledge.py
```

Skrip ini akan mengonversi gejala, sanitasi, dan bahan aktif ke vektor 768 dimensi menggunakan model `text-embedding-004` dan menyimpannya ke tabel `knowledge_base`.

---

## Langkah 4: Pilihan Metode Deployment Server

### Opsi A: Docker & Docker Compose (Direkomendasikan)

Repositori ini sudah dilengkapi dengan `Dockerfile` dan `docker-compose.yml`.

1. **Jalankan Container**:
   ```bash
   docker compose up -d --build
   ```
2. **Periksa Log**:
   ```bash
   docker compose logs -f
   ```
3. **Cek Status Kesehatan**:
   ```bash
   curl http://localhost:8000/health
   ```

---

### Opsi B: VPS Linux (Ubuntu/Debian dengan Systemd & Nginx SSL)

#### 1. Setup Virtualenv & Dependencies
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx
cd /var/www
git clone https://github.com/Ridhorizqullah/chatbot.git tanipintar-bot
cd tanipintar-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
```

#### 2. Buat Service Systemd
Buat file service:
```bash
sudo nano /etc/systemd/system/tanipintar.service
```

Isi konten berikut:
```ini
[Unit]
Description=TaniPintar WhatsApp Bot FastAPI Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/tanipintar-bot
EnvironmentFile=/var/www/tanipintar-bot/.env
ExecStart=/var/www/tanipintar-bot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Aktifkan dan jalankan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tanipintar
sudo systemctl status tanipintar
```

#### 3. Konfigurasi Reverse Proxy Nginx & SSL Certbot
Buat file virtual host:
```bash
sudo nano /etc/nginx/sites-available/tanipintar.conf
```

Isi konten berikut (ganti `bot.domainanda.com` dengan domain Anda):
```nginx
server {
    server_name bot.domainanda.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Aktifkan konfigurasi dan pasang SSL gratis Let's Encrypt:
```bash
sudo ln -s /etc/nginx/sites-available/tanipintar.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d bot.domainanda.com
```

---

### Opsi C: Cloud PaaS (Railway / Render / Google Cloud Run)

1. Hubungkan akun GitHub Anda ke platform PaaS (misal [Railway.app](https://railway.app/)).
2. Pilih repositori `Ridhorizqullah/chatbot`.
3. Masukkan seluruh variabel dari `.env` ke bagian **Environment Variables** di dashboard platform.
4. Start Command: `python main.py`.
5. Platform akan secara otomatis mem-build Dockerfile dan menyediakan URL HTTPS publik.

---

### Opsi D: Testing / Pengembangan Lokal dengan Ngrok

Untuk menguji webhook Meta dari komputer lokal:
1. Jalankan aplikasi secara lokal:
   ```bash
   python main.py
   ```
2. Di terminal terpisah, buat tunnel HTTPS:
   ```bash
   ngrok http 8000
   ```
3. Salin URL HTTPS yang dihasilkan (misal `https://abcd-1234.ngrok-free.app`).

---

## Langkah 5: Pendaftaran Webhook di Meta WhatsApp Dashboard

1. Buka [Meta for Developers](https://developers.facebook.com/) dan pilih App Anda.
2. Di menu navigasi samping, klik **WhatsApp** > **Configuration**.
3. Cari bagian **Webhook**, lalu klik **Edit**:
   - **Callback URL**: `https://bot.domainanda.com/webhook` (atau URL Ngrok Anda)
   - **Verify Token**: Masukkan nilai yang sama dengan `META_WA_VERIFY_TOKEN` di file `.env` (default: `tanipintar_webhook_verify_token_secret`).
4. Klik **Verify and Save**. Server akan menerima GET handshake dan mengembalikan challenge code.
5. Klik **Manage** pada Webhook fields, lalu centang langganan event:
   - ✅ `messages`
6. Selesai! WhatsApp Business Anda kini terhubung ke TaniPintar Bot.

---

## Langkah 6: Verifikasi & Monitoring Operasional

### A. Uji Coba Healthcheck
```bash
curl https://bot.domainanda.com/health
```
Respons yang diharapkan:
```json
{
  "status": "success",
  "message": "TaniPintar Bot API is running healthy.",
  "data": {
    "app_env": "production",
    "version": "1.0.0"
  }
}
```

### B. Uji Kirim Pesan dari WhatsApp
Kirimkan pesan dari nomor WhatsApp pribadi ke nomor WhatsApp Bot Anda:
1. *"Halo"* -> Bot akan membalas dengan daftar 6 layanan utama.
2. *"Berapa harga cabai rawit merah hari ini?"* -> Bot menampilkan harga pasar.
3. *"Bagaimana cuaca di Brebes, aman semprot pestisida?"* -> Bot memberikan analisis cuaca dan advisory semprot.
4. *Kirim foto daun cabai berbercak hitam* -> Bot mengarsipkan foto ke Supabase Storage dan menganalisis penyakit Antraknosa.

### C. Akses Portal Admin Swagger UI
Buka di browser: `https://bot.domainanda.com/docs`
- Gunakan endpoint `POST /api/v1/admin/prices` dengan Header `X-Admin-Key` untuk menginput harga pasar harian.
- Gunakan endpoint `GET /api/v1/admin/consultations?referred_only=true` untuk memantau kasus tanaman petani yang dirujuk ke PPL.
