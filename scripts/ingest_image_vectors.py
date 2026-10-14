import os
import re
import json
import time
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from database.supabase_client import get_supabase
from services.cv_preprocessor import CVPreprocessor
from core.config import settings
from core.logger import logger

# Pemetaan Folder Supabase Storage ke Metadata Penyakit Resmi
STORAGE_METADATA_MAP = {
    "buah_antraknosa": {
        "disease_name": "Antraknosa / Patek",
        "scientific_name": "Colletotrichum capsici",
        "organ": "buah",
        "commodity": "cabai"
    },
    "buah_busuk_phytophthora": {
        "disease_name": "Busuk Buah Phytophthora",
        "scientific_name": "Phytophthora capsici",
        "organ": "buah",
        "commodity": "cabai"
    },
    "buah_lalat_buah": {
        "disease_name": "Serangan Lalat Buah",
        "scientific_name": "Bactrocera dorsalis",
        "organ": "buah",
        "commodity": "cabai"
    },
    "buah_sehat": {
        "disease_name": "Cabai Sehat (Buah Normal)",
        "scientific_name": "Capsicum annuum",
        "organ": "buah",
        "commodity": "cabai"
    },
    "daun_bercak_cercospora": {
        "disease_name": "Bercak Daun Cercospora",
        "scientific_name": "Cercospora capsici",
        "organ": "daun",
        "commodity": "cabai"
    },
    "daun_keriting_thrips": {
        "disease_name": "Keriting Daun / Hama Thrips",
        "scientific_name": "Thrips parvispinus",
        "organ": "daun",
        "commodity": "cabai"
    },
    "daun_sehat": {
        "disease_name": "Cabai Sehat (Daun Normal)",
        "scientific_name": "Capsicum annuum",
        "organ": "daun",
        "commodity": "cabai"
    },
    "daun_virus_gemini": {
        "disease_name": "Virus Kuning Gemini / Bulai",
        "scientific_name": "Pepper Yellow Leaf Curl Virus",
        "organ": "daun",
        "commodity": "cabai"
    },
    "pohon_layu_bakteri": {
        "disease_name": "Layu Bakteri Cabai",
        "scientific_name": "Ralstonia solanacearum",
        "organ": "tanaman_utuh",
        "commodity": "cabai"
    }
}

BUCKET_NAME = "disease-references"


def sanitize_id(text: str) -> str:
    """Mengubah nama file/kategori menjadi ID unik yang aman untuk primary key."""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", text).strip("_")
    return clean[:120]


def get_image_embedding(client: genai.Client, image_bytes: bytes) -> List[float]:
    """Menghasilkan vector embedding 768 dimensi menggunakan model multimodal gemini-embedding-2."""
    part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    res = client.models.embed_content(
        model="gemini-embedding-2",
        contents=part,
        config={"output_dimensionality": 768}
    )
    return res.embeddings[0].values


def list_storage_files_recursive(supabase, prefix: str = "cabai") -> List[str]:
    """Membaca seluruh file foto secara rekursif dari bucket Supabase Storage."""
    file_paths = []
    try:
        items = supabase.storage.from_(BUCKET_NAME).list(prefix)
        for item in items:
            name = item.get("name")
            if not name:
                continue
            full_path = f"{prefix}/{name}"
            # Jika item merupakan folder (tidak memiliki id atau metadata tertentu)
            if item.get("id") is None:
                file_paths.extend(list_storage_files_recursive(supabase, full_path))
            else:
                # File citra
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    file_paths.append(full_path)
    except Exception as e:
        logger.error(f"Gagal membaca folder Storage '{prefix}': {e}")
    return file_paths


def ingest_from_storage(max_per_category: int = 8):
    """
    Mengunduh foto dataset dari Supabase Storage, memvalidasi dengan OpenCV,
    menghasilkan visual vector 768-dim, dan menyimpannya ke Supabase pgvector.
    """
    supabase = get_supabase()
    if not supabase:
        print("ERROR: Supabase Client tidak dapat diinisialisasi. Cek .env.")
        return

    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY belum diset di .env.")
        return

    client = genai.Client(api_key=settings.gemini_api_key)

    print(f"=== 1. MENJELAJAHI FOLDER DI SUPABASE STORAGE: '{BUCKET_NAME}' ===")
    all_files = list_storage_files_recursive(supabase, "cabai")
    print(f"Total file citra ditemukan di Supabase Storage: {len(all_files)} file")

    # Kelompokkan file berdasarkan kategori
    categorized_files: Dict[str, List[str]] = {}
    for fpath in all_files:
        for cat_key in STORAGE_METADATA_MAP.keys():
            if f"/{cat_key}/" in fpath or fpath.startswith(f"cabai/{cat_key}/"):
                categorized_files.setdefault(cat_key, []).append(fpath)
                break

    records_to_insert = []
    category_counts: Dict[str, int] = {}

    print(f"\n=== 2. MENGUNDUH CITRA & GENERATE VISUAL EMBEDDINGS (Maks {max_per_category} per kategori) ===")

    for cat_key, meta in STORAGE_METADATA_MAP.items():
        files = categorized_files.get(cat_key, [])
        selected_files = files[:max_per_category]
        print(f"\n📁 Kategori [{meta['disease_name']}] - {len(selected_files)} exemplars terpilih:")

        for fpath in selected_files:
            filename = os.path.basename(fpath)
            record_id = sanitize_id(f"{cat_key}_{filename}")

            try:
                # Unduh byte citra dari Supabase Storage
                img_bytes = supabase.storage.from_(BUCKET_NAME).download(fpath)
                if not img_bytes:
                    print(f"  ❌ Gagal mengunduh: {fpath}")
                    continue

                # Validasi fisik citra dengan OpenCV Preprocessor
                cv_res = CVPreprocessor.inspect_image(img_bytes)
                if not cv_res.is_valid and cv_res.is_blurry:
                    print(f"  ⚠️ Foto {filename} terdeteksi blur (score: {cv_res.blur_score}). Dilewati.")
                    continue

                # Generate Visual Vector (768 dimensi)
                vec = get_image_embedding(client, img_bytes)

                public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(fpath)

                record = {
                    "id": record_id,
                    "category": cat_key,
                    "disease_name": meta["disease_name"],
                    "scientific_name": meta["scientific_name"],
                    "commodity": meta["commodity"],
                    "organ": meta["organ"],
                    "filename": filename,
                    "storage_path": fpath,
                    "storage_public_url": public_url,
                    "embedding": vec
                }
                records_to_insert.append(record)
                category_counts[cat_key] = category_counts.get(cat_key, 0) + 1
                print(f"  ✅ Sukses: {filename} (Vector 768-dim | {meta['organ']})")
                time.sleep(0.3)  # Anti rate limit
            except Exception as e:
                print(f"  ❌ Error memproses {filename}: {e}")

    print(f"\n=== 3. MENYIMPAN HASIL KE DATABASE SUPABASE (PGVECTOR) ===")
    print(f"Total exemplar siap di-ingest: {len(records_to_insert)} entri")

    # 1. Simpan ke Cache Lokal (JSON)
    cache_path = os.path.join(os.path.dirname(__file__), "..", "data", "visual_gallery_embeddings.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(records_to_insert, f, indent=2)
    print(f"✅ Cache lokal berhasil disimpan: {cache_path}")

    # 2. Coba simpan langsung ke Supabase Table 'disease_image_gallery'
    supabase_success = False
    try:
        # Batch insert per 10 records sesuai best practices
        BATCH_SIZE = 10
        for i in range(0, len(records_to_insert), BATCH_SIZE):
            batch = records_to_insert[i:i + BATCH_SIZE]
            res = supabase.table("disease_image_gallery").upsert(batch).execute()
        print("✅ Seluruh vektor visual berhasil di-upsert ke tabel Supabase 'disease_image_gallery'!")
        supabase_success = True
    except Exception as e:
        print(f"\nℹ️ Catatan Supabase Database: {e}")
        print("Tabel 'disease_image_gallery' belum ada di skema public Supabase Anda.")
        print("Silakan jalankan file SQL berikut di SQL Editor Supabase Dashboard:")
        print("--> database/create_visual_gallery.sql")

    # 3. Generate file SQL Seed opsional jika user ingin run via SQL Editor
    sql_seed_path = os.path.join(os.path.dirname(__file__), "..", "database", "seed_disease_images.sql")
    with open(sql_seed_path, "w", encoding="utf-8") as f:
        f.write("-- SEED DATASET VISUAL RAG FOTO REFERENSI PENYAKIT\n")
        f.write("INSERT INTO public.disease_image_gallery (id, category, disease_name, scientific_name, commodity, organ, filename, storage_path, storage_public_url, embedding)\nVALUES\n")
        val_rows = []
        for r in records_to_insert:
            vec_str = f"'{r['embedding']}'"
            val_rows.append(
                f"('{r['id']}', '{r['category']}', '{r['disease_name']}', '{r['scientific_name']}', '{r['commodity']}', '{r['organ']}', '{r['filename']}', '{r['storage_path']}', '{r['storage_public_url']}', {vec_str})"
            )
        f.write(",\n".join(val_rows))
        f.write("\nON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, storage_public_url = EXCLUDED.storage_public_url;\n")

    print(f"✅ File SQL Seed otomatis telah dibuat: {sql_seed_path}")
    print("\n🎉 INGESTION VISUAL RAG SELESAI!")


if __name__ == "__main__":
    ingest_from_storage(max_per_category=8)
