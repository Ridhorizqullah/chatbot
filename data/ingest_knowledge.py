import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from google import genai
from core.config import settings
from core.logger import logger
from database.supabase_client import get_supabase


def get_embedding(client: genai.Client, text: str) -> List[float]:
    """Menghasilkan vector embedding menggunakan Google GenAI SDK."""
    model = settings.embedding_model.replace("models/", "")
    config = {"output_dimensionality": 768} if "gemini-embedding" in model else None
    response = client.models.embed_content(
        model=model,
        contents=text,
        config=config,
    )
    return response.embeddings[0].values


def ingest_file(client: genai.Client, file_path: Path):
    """Membaca file data JSON penyakit dan memasukkannya ke tabel Supabase knowledge_base."""
    supabase = get_supabase()
    with open(file_path, "r", encoding="utf-8") as f:
        data: List[Dict[str, Any]] = json.load(f)

    logger.info(f"Memproses {len(data)} entri dari {file_path.name}...")

    for item in data:
        # Gabungkan gejala dan deskripsi untuk menghasilkan semantic representation yang kuat
        searchable_text = (
            f"Komoditas: {item['commodity']}. "
            f"Penyakit/Hama: {item['disease_name']} ({item.get('scientific_name', '')}). "
            f"Tipe: {item['pathogen_type']}. "
            f"Gejala: {item['symptoms']} "
            f"Penanganan Mekanis: {item['mechanical_treatment']} "
            f"Sanitasi: {item['sanitation_treatment']} "
            f"Bahan Aktif Kimiawi: {item.get('chemical_actives', '')} "
            f"Rekomendasi Pupuk: {item.get('fertilizer_recommendation', '')}"
        )

        try:
            embedding = get_embedding(client, searchable_text)
            fert = item.get("fertilizer_recommendation")
            prev = item.get("prevention") or ""
            if fert:
                prev = f"{prev} [Rekomendasi Pemupukan: {fert}]" if prev else f"Rekomendasi Pemupukan: {fert}"

            record = {
                "commodity": item["commodity"],
                "disease_name": item["disease_name"],
                "scientific_name": item.get("scientific_name"),
                "pathogen_type": item["pathogen_type"],
                "symptoms": item["symptoms"],
                "mechanical_treatment": item["mechanical_treatment"],
                "sanitation_treatment": item["sanitation_treatment"],
                "chemical_actives": item.get("chemical_actives"),
                "prevention": prev,
                "embedding": embedding
            }

            # Simpan ke Supabase
            supabase.table("knowledge_base").insert(record).execute()
            logger.info(f"Berhasil mengindeks: {item['disease_name']}")
        except Exception as e:
            logger.error(f"Gagal mengindeks {item.get('disease_name')}: {e}")


def main():
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY belum diisi di .env! Harap lengkapi terlebih dahulu.")
        return

    client = genai.Client(api_key=settings.gemini_api_key)
    knowledge_dir = Path(__file__).parent / "knowledge"

    json_files = list(knowledge_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"Tidak ada file json di {knowledge_dir}")
        return

    for file_path in json_files:
        ingest_file(client, file_path)

    logger.info("Ingestion dataset pertanian ke Supabase pgvector selesai!")


if __name__ == "__main__":
    main()
