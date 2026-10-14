import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from google import genai
from google.genai import types
from core.config import settings
from core.logger import logger

DISEASE_METADATA = {
    "buah_antraknosa": {
        "disease_name": "Antraknosa / Patek",
        "scientific_name": "Colletotrichum capsici",
        "organ": "buah",
        "storage_folder": "cabai/buah/buah_antraknosa"
    },
    "buah_busuk_phytophthora": {
        "disease_name": "Busuk Buah Phytophthora",
        "scientific_name": "Phytophthora capsici",
        "organ": "buah",
        "storage_folder": "cabai/buah/buah_busuk_phytophthora"
    },
    "buah_lalat_buah": {
        "disease_name": "Serangan Lalat Buah",
        "scientific_name": "Bactrocera dorsalis",
        "organ": "buah",
        "storage_folder": "cabai/buah/buah_lalat_buah"
    },
    "buah_sehat": {
        "disease_name": "Cabai Sehat (Buah Normal)",
        "scientific_name": "Capsicum annuum",
        "organ": "buah",
        "storage_folder": "cabai/buah/buah_sehat"
    },
    "daun_bercak_cercospora": {
        "disease_name": "Bercak Daun Cercospora",
        "scientific_name": "Cercospora capsici",
        "organ": "daun",
        "storage_folder": "cabai/daun/daun_bercak_cercospora"
    },
    "daun_keriting_thrips": {
        "disease_name": "Keriting Daun / Hama Thrips",
        "scientific_name": "Thrips parvispinus",
        "organ": "daun",
        "storage_folder": "cabai/daun/daun_keriting_thrips"
    },
    "daun_sehat": {
        "disease_name": "Cabai Sehat (Daun Normal)",
        "scientific_name": "Capsicum annuum",
        "organ": "daun",
        "storage_folder": "cabai/daun/daun_sehat"
    },
    "daun_virus_gemini": {
        "disease_name": "Virus Kuning Gemini / Bulai",
        "scientific_name": "Pepper Yellow Leaf Curl Virus",
        "organ": "daun",
        "storage_folder": "cabai/daun/daun_virus_gemini"
    },
    "pohon_layu_bakteri": {
        "disease_name": "Layu Bakteri Cabai",
        "scientific_name": "Ralstonia solanacearum",
        "organ": "tanaman_utuh",
        "storage_folder": "cabai/tanaman_utuh/pohon_layu_bakteri"
    }
}

SUPABASE_PUBLIC_BASE = (
    f"{settings.supabase_url}/storage/v1/object/public/disease-references"
)


def get_image_embedding(client: genai.Client, image_bytes: bytes) -> List[float]:
    """Menghasilkan vector embedding 768 dimensi menggunakan gemini-embedding-2."""
    part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    res = client.models.embed_content(
        model="gemini-embedding-2",
        contents=part,
        config={"output_dimensionality": 768}
    )
    return res.embeddings[0].values


def build_gallery():
    dataset_dir = Path(r"E:\wa bot longchain\data\dataset_foto")
    out_file = Path(r"E:\wa bot longchain\data\visual_gallery_embeddings.json")
    
    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY belum diset.")
        return

    client = genai.Client(api_key=settings.gemini_api_key)
    gallery: List[Dict[str, Any]] = []

    print("=== MEMULAI EKSTRAKSI VISUAL VECTOR RAG ===")
    
    # Ambil maksimal 8 foto per kategori agar galeri seimbang (balanced few-shot gallery)
    MAX_PER_CATEGORY = 8

    for folder_key, meta in DISEASE_METADATA.items():
        # Cari folder di dataset lokal
        matching_dirs = list(dataset_dir.rglob(folder_key))
        if not matching_dirs:
            print(f"Folder {folder_key} tidak ditemukan di {dataset_dir}")
            continue

        target_dir = matching_dirs[0]
        files = [f for f in target_dir.iterdir() if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".webp", ".png"]]
        selected_files = files[:MAX_PER_CATEGORY]

        print(f"Memproses {len(selected_files)} exemplars untuk [{meta['disease_name']}]...")

        for idx, img_path in enumerate(selected_files):
            try:
                with open(img_path, "rb") as f:
                    img_bytes = f.read()

                # Generate visual vector
                vec = get_image_embedding(client, img_bytes)

                storage_path = f"{meta['storage_folder']}/{img_path.name}"
                storage_url = f"{SUPABASE_PUBLIC_BASE}/{storage_path}"

                entry = {
                    "id": f"{folder_key}_{idx+1}",
                    "category": folder_key,
                    "disease_name": meta["disease_name"],
                    "scientific_name": meta["scientific_name"],
                    "organ": meta["organ"],
                    "filename": img_path.name,
                    "storage_path": storage_path,
                    "storage_public_url": storage_url,
                    "embedding": vec
                }
                gallery.append(entry)
                time.sleep(0.3)  # Anti rate-limit
            except Exception as e:
                print(f"  Error pada file {img_path.name}: {e}")

    # Simpan ke file JSON lokal
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(gallery, f, indent=2)

    print(f"\nSUKSES! Berhasil mengindeks {len(gallery)} foto referensi visual ke {out_file.name}")


if __name__ == "__main__":
    build_gallery()
