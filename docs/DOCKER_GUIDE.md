# 🐳 Panduan Docker TaniPintar AI Bot (Development & Production)

Panduan praktis untuk menjalankan, memonitor, dan memperbaiki kode TaniPintar Bot setelah pulang menggunakan Docker.

---

## ⚡ 1. Cara Menjalankan (Quick Start)

Jalankan perintah berikut di terminal root proyek (`e:\wa bot longchain`):

```bash
# Build dan jalankan kedua container (tanipintar-bot & waha) di background
docker compose up -d --build
```

Setelah perintah dijalankan, dua container akan aktif:
1. **`tanipintar-bot`**: Server FastAPI (Port `8000`)
2. **`waha`**: WhatsApp HTTP API GOWS Engine (Port `3000`)

---

## 🔄 2. Fitur Live-Reload (Edit Kode Tanpa Perlu Rebuild!)

Konfigurasi `docker-compose.yml` telah di-update dengan **Volume Bind Mount**:
* Folder kodingan lokal Anda terhubung langsung ke dalam container (`/app`).
* Mode `APP_ENV=development` aktif secara default.
* **Keuntungan:** Ketika Anda mengedit file di folder `services/`, `agents/`, `api/`, atau `core/`, server Uvicorn di dalam container akan **otomatis me-reload kode dalam 1-2 detik** tanpa perlu mematikan atau me-rebuild Docker!

---

## 🔍 3. Cara Memantau Log (Real-time Debugging)

Untuk melihat proses yang sedang berjalan atau mendeteksi error saat pengujian WhatsApp:

```bash
# Melihat log FastAPI bot secara live
docker compose logs -f tanipintar-bot

# Melihat log WAHA WhatsApp engine
docker compose logs -f waha

# Melihat log keduanya sekaligus
docker compose logs -f
```

---

## 📱 4. Menghubungkan WhatsApp (WAHA Dashboard)

1. Buka browser di laptop: [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
2. Login Dashboard (jika diminta):
   * **Username:** `admin`
   * **Password:** (sesuai `.env`, default kosong/no-password)
3. Cek session `chatbot`:
   * Jika status **STOPPED** / **DISCONNECTED**, klik **Start** lalu scan QR Code dengan WhatsApp di ponsel Anda.
   * Jika status **WORKING**, bot sudah terhubung dan siap menerima pesan!

---

## 🧪 5. Menguji Diagnosa Foto Secara Langsung

Kirim foto daun cabai/buah sakit (contoh dari `data/dataset_foto/buah/buah_antraknosa/img_1.jpg`) ke nomor WhatsApp yang terhubung:
1. **OpenCV Preprocessor:** Memeriksa ketajaman foto ($<15\text{ms}$).
2. **Visual RAG:** Mengambil top-3 foto termirip dari Supabase Storage.
3. **Pesan Balasan WhatsApp:**
   - Nama penyakit & patogen ilmiah.
   - Skor kemiripan visual (%) & link foto pembanding Supabase.
   - 3 Pilar penanganan (Mekanis, Sanitasi, Kimiawi).

---

## 🛠️ 6. Perintah Berguna Lainnya

```bash
# Menghentikan container sementara
docker compose stop

# Menyalakan kembali tanpa rebuild
docker compose start

# Mematikan container dan menghapus network
docker compose down

# Masuk ke dalam terminal shell container bot untuk inspeksi langsung
docker compose exec tanipintar-bot bash
```
