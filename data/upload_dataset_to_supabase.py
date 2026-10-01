import os
import re
from pathlib import Path
from typing import Dict, Any, List
from database.supabase_client import get_supabase
from core.logger import logger

# Pemetaan folder dataset lokal ke nama penyakit standar TaniPintar
FOLDER_MAPPING: Dict[str, Dict[str, str]] = {
    "buah/buah_antraknosa": {
        "commodity": "cabai",
        "disease_name": "Antraknosa / Patek",
        "description": "Gejala infeksi jamur Colletotrichum capsici pada buah cabai, bercak melingkar melekuk basah kehitaman."
    },
    "buah/buah_busuk_phytophthora": {
        "commodity": "cabai",
        "disease_name": "Busuk Buah Phytophthora",
        "description": "Gejala busuk basah kecokelatan hingga kehitaman pada buah cabai akibat jamur Phytophthora capsici."
    },
    "buah/buah_lalat_buah": {
        "commodity": "cabai",
        "disease_name": "Serangan Lalat Buah (Bactrocera)",
        "description": "Gejala tusukan ovipositor lalat buah, timbul titik hitam dan buah menguning serta gugur prematur."
    },
    "buah/buah_sehat": {
        "commodity": "cabai",
        "disease_name": "Cabai Sehat (Buah Normal)",
        "description": "Buah cabai sehat, mengkilap, padat, dan bebas dari cacat atau infeksi patogen."
    },
    "daun/daun_bercak_cercospora": {
        "commodity": "cabai",
        "disease_name": "Bercak Daun Cercospora (Mata Katak)",
        "description": "Bercak bulat konsentris berwarna cokelat kelabu dengan titik putih di pusat helaian daun cabai."
    },
    "daun/daun_keriting_thrips": {
        "commodity": "cabai",
        "disease_name": "Serangan Hama Thrips (Keriting Daun)",
        "description": "Helaian daun cabai mengeriting melengkung ke atas dengan bercak keperakan akibat hisapan nimfa thrips."
    },
    "daun/daun_virus_gemini": {
        "commodity": "cabai",
        "disease_name": "Penyakit Bulai / Virus Kuning Gemini",
        "description": "Klorosis kuning cerah menyeluruh pada urat daun dan permukaan helai daun tanaman cabai."
    },
    "daun/daun_sehat": {
        "commodity": "cabai",
        "disease_name": "Cabai Sehat (Daun Normal)",
        "description": "Daun cabai hijau segar, membuka sempurna, tanpa gejala bercak atau keriting."
    },
    "tanaman utuh/pohon_layu_bakteri": {
        "commodity": "cabai",
        "disease_name": "Layu Bakteri",
        "description": "Kelayuan serentak mendadak pada tajuk tanaman cabai saat daun masih hijau segar akibat Ralstonia solanacearum."
    }
}


def sanitize_filename(name: str) -> str:
    """Membersihkan nama file agar aman untuk Supabase Storage URL."""
    clean = re.sub(r'[^a-zA-Z0-9_\.-]', '_', name)
    return clean.lower()


def upload_dataset():
    supabase = get_supabase()
    if not supabase:
        logger.error("Supabase Client gagal diinisialisasi. Periksa SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY di .env.")
        return

    base_dataset_dir = Path(__file__).parent / "dataset_foto"
    if not base_dataset_dir.exists():
        logger.error(f"Folder dataset tidak ditemukan di: {base_dataset_dir}")
        return

    bucket_name = "disease-references"
    total_uploaded = 0
    total_records = 0

    logger.info("Memulai proses upload dataset foto ke Supabase Storage & Database...")

    for rel_folder, meta in FOLDER_MAPPING.items():
        folder_path = base_dataset_dir / Path(rel_folder)
        if not folder_path.exists():
            logger.warning(f"Subfolder {rel_folder} tidak ditemukan, dilewati.")
            continue

        files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".jfif"]]
        
        # Batasi daun sehat agar tidak terlalu membebani upload (~25 sampel representatif)
        if "daun_sehat" in rel_folder and len(files) > 25:
            files = files[:25]

        logger.info(f"📂 Mengunggah {len(files)} foto untuk '{meta['disease_name']}'...")

        for file_path in files:
            clean_name = sanitize_filename(file_path.name)
            storage_path = f"{meta['commodity']}/{rel_folder.replace(' ', '_')}/{clean_name}"

            try:
                with open(file_path, "rb") as img_f:
                    file_bytes = img_f.read()

                suffix = file_path.suffix.lower()
                if suffix == ".png":
                    content_type = "image/png"
                elif suffix == ".webp":
                    content_type = "image/webp"
                else:
                    content_type = "image/jpeg"

                # Upload ke Supabase Storage
                supabase.storage.from_(bucket_name).upload(
                    path=storage_path,
                    file=file_bytes,
                    file_options={"content-type": content_type, "upsert": "true"}
                )

                # Dapatkan URL publik
                public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
                total_uploaded += 1

                # Simpan metadata ke tabel disease_reference_images
                record = {
                    "commodity": meta["commodity"],
                    "disease_name": meta["disease_name"],
                    "image_url": public_url,
                    "description": meta["description"]
                }
                supabase.table("disease_reference_images").insert(record).execute()
                total_records += 1

            except Exception as e:
                logger.error(f"Gagal mengunggah {file_path.name}: {e}")

    logger.info(f"🎉 Selesai! Berhasil mengunggah {total_uploaded} foto ke Storage dan {total_records} record ke tabel 'disease_reference_images'.")


if __name__ == "__main__":
    upload_dataset()
