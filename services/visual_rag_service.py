import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
from google import genai
from google.genai import types
from core.config import settings
from core.logger import logger
from database.supabase_client import get_supabase


@dataclass
class VisualMatchResult:
    """Hasil pencarian kemiripan visual terhadap pustaka foto referensi."""
    has_match: bool
    best_disease_name: str
    scientific_name: str
    organ: str
    similarity_percentage: float
    reference_storage_url: str
    top_matches: List[Dict[str, Any]]
    visual_reasoning: str


class VisualRAGService:
    """
    Service Visual RAG (Image-to-Image Vector Similarity Search).
    Mencari foto referensi paling identik di Supabase Storage / Gallery
    menggunakan perbandingan vektor kosinus (Cosine Similarity).
    """

    def __init__(self):
        self.gallery_file = Path(__file__).resolve().parent.parent / "data" / "visual_gallery_embeddings.json"
        self._gallery_cache: List[Dict[str, Any]] = []
        self._embeddings_matrix: Optional[np.ndarray] = None
        self.client: Optional[genai.Client] = None

        if settings.gemini_api_key:
            self.client = genai.Client(api_key=settings.gemini_api_key)

        self._load_gallery()

    def _load_gallery(self):
        """Memuat pustaka vektor citra ke dalam memori RAM untuk pencarian instan (< 10ms)."""
        if not self.gallery_file.exists():
            logger.warning(f"[VisualRAG] File galeri vektor belum ditemukan: {self.gallery_file}")
            return

        try:
            with open(self.gallery_file, "r", encoding="utf-8") as f:
                self._gallery_cache = json.load(f)

            if self._gallery_cache:
                vectors = [item["embedding"] for item in self._gallery_cache]
                mat = np.array(vectors, dtype=np.float32)
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms[norms == 0] = 1e-10
                self._embeddings_matrix = mat / norms
                logger.info(f"[VisualRAG] Berhasil memuat {len(self._gallery_cache)} vektor referensi visual.")
        except Exception as e:
            logger.error(f"[VisualRAG] Gagal memuat galeri visual: {e}")

    def embed_image(self, image_bytes: bytes) -> Optional[np.ndarray]:
        """Menghasilkan representasi vektor visual citra (768 dimensi) menggunakan gemini-embedding-2."""
        if not self.client:
            return None
        try:
            part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            res = self.client.models.embed_content(
                model="gemini-embedding-2",
                contents=part,
                config={"output_dimensionality": 768}
            )
            vec = np.array(res.embeddings[0].values, dtype=np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec
        except Exception as e:
            logger.error(f"[VisualRAG] Gagal ekstraksi embedding gambar: {e}")
            return None

    def _search_supabase_rpc(
        self,
        query_vec: np.ndarray,
        top_k: int = 3,
        organ_filter: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Mencoba pencarian langsung ke Supabase pgvector melalui stored procedure RPC match_disease_images."""
        supabase = get_supabase()
        if not supabase:
            return None
        try:
            params = {
                "query_image_embedding": query_vec.tolist(),
                "match_threshold": 0.65,
                "match_count": top_k,
                "filter_organ": organ_filter.lower() if organ_filter else None
            }
            res = supabase.rpc("match_disease_images", params).execute()
            if res.data:
                formatted = []
                for row in res.data:
                    sim = float(row.get("similarity", 0.0))
                    formatted.append({
                        "disease_name": row.get("disease_name"),
                        "scientific_name": row.get("scientific_name", ""),
                        "organ": row.get("organ"),
                        "similarity": round(sim, 4),
                        "similarity_pct": round(sim * 100, 1),
                        "storage_url": row.get("storage_public_url", ""),
                        "filename": row.get("id", "")
                    })
                return formatted
        except Exception as e:
            logger.debug(f"[VisualRAG] Supabase RPC belum diaktifkan di database, menggunakan memori vektor lokal: {e}")
        return None

    def search_similar_images(
        self,
        image_bytes: bytes,
        top_k: int = 3,
        organ_filter: Optional[str] = None
    ) -> VisualMatchResult:
        """
        Mencari foto penyakit paling mirip dari galeri referensi Supabase.
        Mencoba query Supabase pgvector terlebih dahulu; jika belum ada tabel, 
        otomatis fallback ke in-memory vectorized Cosine Similarity (<10ms).
        """
        query_vec = self.embed_image(image_bytes)
        if query_vec is None:
            return VisualMatchResult(
                has_match=False,
                best_disease_name="Gagal Ekstraksi",
                scientific_name="",
                organ=organ_filter or "umum",
                similarity_percentage=0.0,
                reference_storage_url="",
                top_matches=[],
                visual_reasoning="Gagal memproses fitur visual citra."
            )

        # 1. Coba pencarian via Supabase RPC pgvector
        rpc_matches = self._search_supabase_rpc(query_vec, top_k, organ_filter)
        if rpc_matches:
            best = rpc_matches[0]
            return VisualMatchResult(
                has_match=best["similarity"] >= 0.70,
                best_disease_name=best["disease_name"],
                scientific_name=best["scientific_name"],
                organ=best["organ"],
                similarity_percentage=best["similarity_pct"],
                reference_storage_url=best["storage_url"],
                top_matches=rpc_matches,
                visual_reasoning=(
                    f"Kecocokan visual tertinggi ({best['similarity_pct']}%) teridentifikasi via Supabase pgvector "
                    f"mirip dengan sampel referensi '{best['disease_name']}' pada organ {best['organ']}."
                )
            )

        # 2. Fallback: Pencarian Vektor Lokal In-Memory (NumPy dot product)
        if self._embeddings_matrix is None or len(self._gallery_cache) == 0:
            return VisualMatchResult(
                has_match=False,
                best_disease_name="Tidak Ada Referensi",
                scientific_name="",
                organ=organ_filter or "umum",
                similarity_percentage=0.0,
                reference_storage_url="",
                top_matches=[],
                visual_reasoning="Pustaka vektor visual belum terindeks."
            )

        similarities = np.dot(self._embeddings_matrix, query_vec)
        sorted_indices = np.argsort(similarities)[::-1]

        top_matches = []
        for idx in sorted_indices:
            item = self._gallery_cache[idx]
            sim_score = float(similarities[idx])

            if organ_filter and organ_filter in ["buah", "daun", "tanaman_utuh"]:
                if item.get("organ") != organ_filter and sim_score < 0.85:
                    continue

            top_matches.append({
                "disease_name": item["disease_name"],
                "scientific_name": item.get("scientific_name", ""),
                "organ": item["organ"],
                "similarity": round(sim_score, 4),
                "similarity_pct": round(sim_score * 100, 1),
                "storage_url": item["storage_public_url"],
                "filename": item.get("filename", "")
            })

            if len(top_matches) >= top_k:
                break

        if not top_matches:
            top_matches = [{
                "disease_name": self._gallery_cache[sorted_indices[0]]["disease_name"],
                "scientific_name": self._gallery_cache[sorted_indices[0]].get("scientific_name", ""),
                "organ": self._gallery_cache[sorted_indices[0]]["organ"],
                "similarity": round(float(similarities[sorted_indices[0]]), 4),
                "similarity_pct": round(float(similarities[sorted_indices[0]]) * 100, 1),
                "storage_url": self._gallery_cache[sorted_indices[0]]["storage_public_url"],
                "filename": self._gallery_cache[sorted_indices[0]].get("filename", "")
            }]

        best = top_matches[0]
        has_match = best["similarity"] >= 0.70

        reasoning = (
            f"Kecocokan visual tertinggi ({best['similarity_pct']}%) teridentifikasi mirip dengan "
            f"sampel referensi '{best['disease_name']}' pada organ {best['organ']}."
        )

        logger.info(
            f"[VisualRAG] Hasil pencarian: {best['disease_name']} ({best['similarity_pct']}%) "
            f"| Storage URL: {best['storage_url']}"
        )

        return VisualMatchResult(
            has_match=has_match,
            best_disease_name=best["disease_name"],
            scientific_name=best["scientific_name"],
            organ=best["organ"],
            similarity_percentage=best["similarity_pct"],
            reference_storage_url=best["storage_url"],
            top_matches=top_matches,
            visual_reasoning=reasoning
        )
