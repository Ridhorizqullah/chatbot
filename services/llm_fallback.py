"""
Cadangan LLM via Tencent Cloud TokenHub (API kompatibel OpenAI Chat Completions).

Dipakai HANYA untuk permintaan teks ketika semua model Gemini gagal
(misal kena limit 429 / error 5xx). Diagnosis foto dan embedding tetap memakai Gemini.
"""
import json
import re
from typing import List, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from core.config import settings
from core.logger import logger

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def is_enabled() -> bool:
    """True jika TOKENHUB_API_KEY sudah diisi di .env."""
    return bool(settings.tokenhub_api_key)


def _candidate_models() -> List[str]:
    return [m.strip() for m in settings.tokenhub_models.split(",") if m.strip()]


def _extract_json(text: str) -> Optional[dict]:
    """Ambil objek JSON dari jawaban model (toleran terhadap ```json ... ``` atau teks pembuka)."""
    cleaned = _CODE_FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


def generate_structured(prompt: str, schema: Type[T]) -> Optional[T]:
    """
    Meminta TokenHub menghasilkan JSON sesuai skema Pydantic, lalu memvalidasinya.
    Mengembalikan None jika TokenHub nonaktif atau semua model cadangan gagal.
    """
    if not is_enabled():
        return None

    system_msg = (
        "Anda adalah asisten pertanian TaniPintar. Jawab dalam Bahasa Indonesia.\n"
        "Balas HANYA dengan satu objek JSON valid (tanpa teks lain, tanpa markdown) "
        "yang mematuhi JSON Schema berikut:\n"
        f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )
    url = f"{settings.tokenhub_base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {settings.tokenhub_api_key}"}

    for model in _candidate_models():
        try:
            with httpx.Client(timeout=settings.tokenhub_timeout_seconds) as client:
                res = client.post(url, headers=headers, json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 2048,
                })
            if res.status_code != 200:
                logger.warning(f"[TokenHub] Model '{model}' gagal (HTTP {res.status_code}): {res.text[:300]}")
                continue

            content = res.json()["choices"][0]["message"].get("content") or ""
            data = _extract_json(content)
            if data is None:
                logger.warning(f"[TokenHub] Model '{model}' tidak mengembalikan JSON valid.")
                continue

            result = schema.model_validate(data)
            logger.info(f"[TokenHub] Jawaban cadangan berhasil dari model '{model}'.")
            return result
        except ValidationError as e:
            logger.warning(f"[TokenHub] JSON dari '{model}' tidak cocok dengan skema {schema.__name__}: {e.error_count()} error.")
        except Exception as e:
            logger.warning(f"[TokenHub] Error memanggil model '{model}': {e}")

    logger.error("[TokenHub] Semua model cadangan TokenHub gagal.")
    return None
