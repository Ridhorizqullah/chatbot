#!/bin/bash
set -e

echo "=========================================="
echo "🚀 SETUP OTOMATIS TANIPINTAR DI LIGHTHOUSE"
echo "=========================================="

# 1. Setup Swap Memory (3 GB) agar RAM 2 GB aman dari OOM
if [ $(swapon --show | wc -l) -le 1 ]; then
    echo "⚙️ Menyiapkan Swap Memory 3 GB..."
    sudo fallocate -l 3G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "✅ Swap Memory 3 GB berhasil diaktifkan."
else
    echo "✅ Swap Memory sudah aktif."
fi

# 2. Verifikasi Docker
if ! command -v docker &> /dev/null; then
    echo "⚙️ Menginstall Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
fi

# 3. Masuk ke direktori aplikasi
APP_DIR="/opt/tanipintar"
if [ ! -d "$APP_DIR" ]; then
    echo "📥 Mengunduh repository..."
    sudo git clone https://github.com/Ridhorizqullah/chatbot.git $APP_DIR
    sudo chown -R $USER:$USER $APP_DIR
fi

cd $APP_DIR

# 4. Cek file .env
if [ ! -f ".env" ]; then
    echo "⚠️ File .env belum ditemukan. Menyalin dari .env.example..."
    cp .env.example .env
    echo "❗ PENTING: Silakan edit file .env (nano .env) dan masukkan API KEY Anda."
fi

# 5. Jalankan Docker Compose
echo "🚀 Membangun dan menjalankan container (Bot & WAHA)..."
docker compose up -d --build

echo "=========================================="
echo "🎉 DEPLOYMENT SELESAI!"
echo "Status container:"
docker compose ps
echo ""
echo "📱 Akses Dashboard WAHA: http://$(curl -s ifconfig.me):3000/dashboard"
echo "🤖 Healthcheck Bot API: http://$(curl -s ifconfig.me):8000/health"
echo "=========================================="
