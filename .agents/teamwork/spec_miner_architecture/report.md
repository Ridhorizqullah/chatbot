# Technical Specification & Architecture Alignment Report: TaniPintar Bot

**Author**: Specification Miner (Codebase & Architecture Alignment)  
**Date**: 2026-10-01T17:45:00Z  
**Target Document**: `laporan.md`  
**Authoritative Codebase**: `E:\wa bot longchain\` (`agents/`, `api/`, `core/`, `database/`, `services/`, `data/`, `tests/`, `graph_builder.py`, `main.py`)

---

## 1. Executive Summary

A comprehensive architectural and technical specification audit was performed across the TaniPintar Bot codebase against `laporan.md`. While the core codebase is well-structured and fully functional across its 6 MVP services and 13 unit/integration tests, **multiple critical misalignments, security vulnerabilities, and architectural discrepancies** were discovered in `laporan.md`:

1. **Security Vulnerability (Critical - R1)**: A live plaintext API key (`WEATHER_API_KEY=76d7a4136a6948e8ac464008250810`) is hardcoded in `laporan.md` across three separate locations (Mermaid diagram line 90, credential table line 241, and advisory description line 317).
2. **LangGraph StateGraph Execution Discrepancy**: `laporan.md` states in diagram 2.1 (lines 98-99) that the `audit_saver` node sends WhatsApp messages directly to WAHA/Meta API. In code reality (`graph_builder.py` and `api/routes/whatsapp.py`), `audit_saver_node` purely writes audit records to Supabase and routes to `END`. The WhatsApp message is actually dispatched asynchronously by `process_incoming_message` in FastAPI background tasks.
3. **Mermaid StateGraph Modeling Discrepancy**: Diagram 2.2 nests service nodes (`vision`, `weather`, `price`, etc.) inside a composite `state router { ... }`. In LangGraph, `router` is a singular node that returns an intent string, evaluated by `route_intent()` conditional edges to 7 distinct, top-level service nodes.
4. **Database DDL Omissions**: `database/schema.sql` completely omits the `disease_reference_images` table definition (required by `upload_dataset_to_supabase.py` and `repository.py`) and is missing the `followup_notes` column in `consultation_audits` (required by `api/routes/admin.py`). Furthermore, `laporan.md` truncates the `match_knowledge` RPC function signature.
5. **Weather Multi-tier Fallback**: `laporan.md` describes a simple WeatherAPI-to-Open-Meteo switch. The code reality reveals a resilient 3-layer architecture: (1) WeatherAPI with 10s timeout and error handling, (2) Open-Meteo with 2-tier geocoding (12-city coordinate map + Geocoding API + Karawang default), and (3) hardcoded local agronomic double-fallback when both network providers fail.
6. **Directory & Dependency Completeness**: `laporan.md` §11 omits key root files including `deploy.md`, `progres.md`, `README.md`, `.dockerignore`, `uv.lock`, `skills-lock.json`, and runtime directories `logs/` and `waha_data/`.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | LangGraph | `router_node` | Classifies user intent from WhatsApp text message or presence of `media_id` | `TaniState` with `user_message` and optional `media_id` | Dict with `intent` ("vision_diagnosis", "history", "weather", "market_price", "fertilizer", "greeting", or "diagnosis") and `crop_context` | Defaults to `"diagnosis"` with detected crop context (`cabai`/`padi`) | `graph_builder.py:50-96` |
| 2 | LangGraph | `vision_node` | Handles image downloads from WAHA/Meta, stores to Supabase Storage, and runs multimodal Gemini Vision diagnosis | `TaniState` with `media_id`, `user_message`, `phone_number` | Dict with `media_url`, `diagnosis_result`, `crop_context` | Returns warning message if media download fails | `graph_builder.py:98-131` |
| 3 | LangGraph | `diagnosis_node` | Executes RAG text query against 11 crop diseases using Gemini Embeddings and pgvector `match_knowledge` RPC | `TaniState` with `user_message` and `crop_context` | Dict with `diagnosis_result` (`DiseaseDiagnosisResult`) | Fallback structured error response if API key unconfigured | `graph_builder.py:133-140`, `agents/diagnosis_agent.py:68-131` |
| 4 | LangGraph | `price_node` | Retrieves commodity pricing (farmgate and consumer prices) from Supabase or deterministic daily variance generator | `TaniState` with `user_message` | Dict with `price_result` (`CommodityPriceResult`) | Falls back to national baseline formula with regional multipliers | `graph_builder.py:142-147`, `services/price_service.py:57-141` |
| 5 | LangGraph | `history_node` | Queries farmer's last 3 consultation records from `consultation_audits` in Supabase | `TaniState` with `phone_number` | Dict with `history_result` (list of audit records) | Returns empty list if no history or DB offline | `graph_builder.py:149-154`, `database/repository.py:98-116` |
| 6 | LangGraph | `weather_node` | Extracts location query, resolves coordinates, queries WeatherAPI/Open-Meteo, and generates agronomic spray/fertilizer advisories | `TaniState` with `user_message` | Dict with `weather_result` (`WeatherAdvisoryResult`) | Double-fallback to static agronomic estimation if all weather APIs fail | `graph_builder.py:156-167`, `services/weather_service.py:136-205` |
| 7 | LangGraph | `fertilizer_node` | Calculates dosage and nutrients based on crop phase (Vegetatif vs Generatif) and generates pesticide companion | `TaniState` with `user_message` and `crop_context` | Dict with `fertilizer_result` (`FertilizerRecommendationResult`) | Returns deterministic Kementan guideline baseline if Gemini client uninitialized | `graph_builder.py:169-175`, `agents/fertilizer_agent.py:19-109` |
| 8 | LangGraph | `greeting_node` | Emits interactive guide for the 6 MVP services and usage instructions | `TaniState` | Dict with formatted `final_response` WhatsApp markdown | N/A (Static verified text) | `graph_builder.py:177-196` |
| 9 | LangGraph / Guardrail | `format_and_guardrail_node` | Enforces WhatsApp Markdown formatting, verifies crop eligibility, applies confidence threshold (`< 0.70`), and appends official reference image URLs | `TaniState` containing individual service outputs | Dict with `final_response` | Replaces diagnosis with `SAFE_FALLBACK_MESSAGE` if confidence `< 0.70` or `rujuk_ke_ppl=True` | `graph_builder.py:198-316` |
| 10 | LangGraph / Storage | `audit_saver_node` | Persists consultation audit log to `consultation_audits` and updates `chat_sessions` in Supabase | `TaniState` | Empty dict `{}` (Side-effect DB write) | Catches exception and logs warning without blocking user response | `graph_builder.py:318-342` |
| 11 | Database / RPC | `match_knowledge` | Supabase PostgreSQL stored procedure for cosine similarity RAG search using pgvector | `query_embedding VECTOR(768)`, `match_threshold FLOAT (0.65)`, `match_count INT (4)`, `filter_commodity TEXT (NULL)` | `TABLE (...)` with 11 metadata fields and `similarity FLOAT` | Returns empty table if no records match threshold or commodity | `database/schema.sql:32-73` |
| 12 | Database / Storage | `disease_reference_images` | Catalog of 292 field dataset images uploaded to Supabase Storage bucket `disease-references` | `disease_name` lookup query | `image_url` string | Returns `None` if no matching image found | `database/repository.py:118-139`, `data/upload_dataset_to_supabase.py` |
| 13 | External API | WeatherAPI.com | Primary weather forecasting provider with Indonesian localization (`lang=id`) | `location_query`, `api_key` | JSON with temperature, humidity, precipitation, and rain probability | Fallback to Open-Meteo on non-200 HTTP response or timeout | `services/weather_service.py:61-112` |
| 14 | External API | Open-Meteo & Geocoding | Free fallback weather forecasting and coordinate resolution for Indonesian regencies | Lat/Lon coordinates, hourly/current weather parameters | Current temp, humidity, precipitation, weather code, and rain probability | Fallback to hardcoded default coordinates (Karawang: -6.3060, 107.3019) and hardcoded estimate | `services/weather_service.py:113-193` |
| 15 | REST API | FastAPI Webhooks | Dual WhatsApp webhook receiving Meta Graph API (`/webhook`) and WAHA WebJS (`/webhook/waha`) | HTTP POST JSON payload from Meta/WAHA | Immediate HTTP 200 JSON (`< 200ms`), message queued to FastAPI `BackgroundTasks` | Drops duplicates (2,000 LRU message ID cache) and ignores self-sent messages | `api/routes/whatsapp.py:66-182` |
| 16 | REST API | Admin Portal CRUD | Protected management endpoints for market prices (CRUD) and consultation audits (GET, PATCH, DELETE) | HTTP request with `X-Admin-Key` header | Standardized JSON `{status, message, data}` | Returns HTTP 401 if key invalid (bypassed in `development` mode) | `api/routes/admin.py:21-169` |

---

## 3. Edge Cases & Boundary Conditions

| # | Feature | Input / Condition | Observed Codebase Behavior |
|---|---------|-------------------|----------------------------|
| 1 | Crop Guardrail | User sends query/image of oil palm, apple, or durian | `is_supported_crop=False`, `confidence_score=0.0`. `format_and_guardrail_node` returns polite rejection: *"Mohon maaf Bapak/Ibu Petani, layanan konsultasi foto TaniPintar saat ini KHUSUS didedikasikan untuk tanaman CABAI dan PADI..."*. Audit record is not logged to `consultation_audits`. |
| 2 | Confidence Threshold | AI inference returns `confidence_score = 0.69` | `confidence < settings.confidence_threshold` triggers. System discards speculative diagnosis and returns verbatim `SAFE_FALLBACK_MESSAGE`. Sets `is_referred_to_ppl=True` in audit database. |
| 3 | Confidence Threshold | AI inference returns `confidence_score = 0.70` | Passes guardrail check (`confidence < 0.70` is False). Outputs 3 Pillars treatment plan and appends official reference image URL. |
| 4 | Weather API Key Missing | `settings.weather_api_key=""` | `_get_weatherapi_forecast` immediately returns `None` without HTTP call. Smoothly executes Layer 2 (Open-Meteo). |
| 5 | Unknown Weather City | User asks for weather in unrecognized village | `DEFAULT_COORDINATES` lookup fails -> Open-Meteo Geocoding API fails -> Falls back to `(-6.3060, 107.3019, "Karawang (Default Sentra Padi)")`. |
| 6 | Total Weather Failure | Both WeatherAPI.com and Open-Meteo down / offline | Double fallback executes in `except Exception`: returns `"Cerah Berawan (Estimasi)"`, 29°C, 78% humidity, 25% rain probability, and safe morning spraying advice. Zero downtime. |
| 7 | Image Without Caption | WhatsApp user uploads photo with empty caption | `api/routes/whatsapp.py` injects default caption: `"Tolong diagnosa gejala penyakit tanaman pada foto ini."` before dispatching to LangGraph. |
| 8 | WAHA WebJS Disconnection | WAHA session crashes or returns HTTP 422 "does not exist" | `whatsapp_service.py` auto-discovers working sessions via `GET /api/sessions` and retries delivery on any active `WORKING` session. |
| 9 | Duplicate Webhook | WhatsApp gateway retries delivery of same message ID | `_PROCESSED_MESSAGE_IDS` set in `api/routes/whatsapp.py` filters duplicate IDs and returns `{"status": "success", "message": "Duplicate message ignored"}`. |
| 10 | Admin Auth in Dev | `APP_ENV=development` with missing `X-Admin-Key` | `verify_admin_key` skips authentication check when `settings.app_env == "development"`, allowing seamless local testing. |

---

## 4. Deep Architectural Reality vs. `laporan.md`

### 4.1 LangGraph StateGraph Architecture

#### Exact State Definition (`graph_builder.py:22-35`):
```python
class TaniState(TypedDict):
    phone_number: str
    user_message: str
    media_id: Optional[str]
    media_url: Optional[str]
    intent: Literal["diagnosis", "vision_diagnosis", "market_price", "history", "weather", "fertilizer", "greeting", "fallback"]
    crop_context: Optional[str]
    diagnosis_result: Optional[Dict[str, Any]]
    price_result: Optional[Dict[str, Any]]
    weather_result: Optional[Dict[str, Any]]
    fertilizer_result: Optional[Dict[str, Any]]
    history_result: Optional[List[Dict[str, Any]]]
    final_response: str
```

#### Graph Topography:
- **Total Nodes**: 10
  - Entry node: `router` (`router_node`)
  - Worker nodes (7): `vision`, `diagnosis`, `price`, `history`, `weather`, `fertilizer`, `greeting`
  - Processing & Formatting node: `formatter` (`format_and_guardrail_node`)
  - Persistence node: `audit_saver` (`audit_saver_node`)
- **Conditional Router**: `route_intent(state: TaniState) -> str`
  - Maps `intent` to `"vision"`, `"price"`, `"history"`, `"weather"`, `"fertilizer"`, `"greeting"`, or `"diagnosis"`.
- **Edge Connections**:
  - `START` $\rightarrow$ `router`
  - `router` $\xrightarrow{\text{conditional}}$ `[vision, diagnosis, price, history, weather, fertilizer, greeting]`
  - Each of the 7 worker nodes $\rightarrow$ `formatter`
  - `formatter` $\rightarrow$ `audit_saver`
  - `audit_saver` $\rightarrow$ `END`

#### Architectural Discrepancy in `laporan.md`:
1. In `laporan.md` Diagram 2.1 (lines 98-99), `AuditSaver` is drawn sending messages to WAHA and Meta API. In code reality, `audit_saver` only writes to Supabase. The asynchronous HTTP webhook worker `process_incoming_message` receives the compiled graph output `result["final_response"]` and calls `whatsapp_service.send_text_message`.
2. In `laporan.md` Diagram 2.2 (lines 113-122), worker nodes are drawn inside `state router { ... }`. In LangGraph, worker nodes are peer nodes outside the router, connected via conditional edges.

---

### 4.2 Database Schema & pgvector RPC Reality

#### Authoritative DDL Specifications (`database/schema.sql`):

1. **`knowledge_base`**:
   - `id BIGSERIAL PRIMARY KEY`
   - `commodity VARCHAR(50) NOT NULL` (`cabai` / `padi`)
   - `disease_name VARCHAR(150) NOT NULL`
   - `scientific_name VARCHAR(150)`
   - `pathogen_type VARCHAR(50) NOT NULL` (`Jamur`, `Bakteri`, `Virus`, `Hama`)
   - `symptoms TEXT NOT NULL`
   - `mechanical_treatment TEXT NOT NULL`
   - `sanitation_treatment TEXT NOT NULL`
   - `chemical_actives TEXT`
   - `prevention TEXT`
   - `embedding VECTOR(768)`
   - `created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL`
   - Index: `knowledge_base_embedding_idx USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)`

2. **`chat_sessions`**:
   - `phone_number VARCHAR(30) PRIMARY KEY`
   - `current_state JSONB DEFAULT '{}'::jsonb`
   - `last_crop_context VARCHAR(50)`
   - `updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL`

3. **`consultation_audits`**:
   - `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   - `phone_number VARCHAR(30) NOT NULL`
   - `crop_type VARCHAR(50)`
   - `suspected_disease VARCHAR(150)`
   - `confidence_score FLOAT NOT NULL`
   - `is_referred_to_ppl BOOLEAN DEFAULT FALSE`
   - `media_url TEXT`
   - `farmer_query TEXT NOT NULL`
   - `bot_recommendation JSONB NOT NULL`
   - `created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL`
   - Indexes: `idx_consultation_phone`, `idx_consultation_created_at`

4. **`market_prices`**:
   - `id BIGSERIAL PRIMARY KEY`
   - `price_date DATE NOT NULL`
   - `commodity VARCHAR(100) NOT NULL`
   - `province VARCHAR(100) NOT NULL`
   - `farmgate_price INT NOT NULL`
   - `consumer_price INT NOT NULL`
   - `unit VARCHAR(20) DEFAULT 'kg'`
   - `source VARCHAR(100) DEFAULT 'Sistem Otomatis / Admin'`
   - `notes TEXT`
   - `created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL`
   - Constraint: `UNIQUE (price_date, commodity, province)`
   - Index: `idx_market_prices_lookup`

5. **RPC Function `match_knowledge` (`database/schema.sql:32-73`)**:
   ```sql
   CREATE OR REPLACE FUNCTION match_knowledge (
       query_embedding VECTOR(768),
       match_threshold FLOAT DEFAULT 0.65,
       match_count INT DEFAULT 4,
       filter_commodity TEXT DEFAULT NULL
   )
   RETURNS TABLE (
       id BIGINT,
       commodity VARCHAR(50),
       disease_name VARCHAR(150),
       scientific_name VARCHAR(150),
       pathogen_type VARCHAR(50),
       symptoms TEXT,
       mechanical_treatment TEXT,
       sanitation_treatment TEXT,
       chemical_actives TEXT,
       prevention TEXT,
       similarity FLOAT
   )
   LANGUAGE plpgsql
   AS $$
   BEGIN
       RETURN QUERY
       SELECT
           kb.id, kb.commodity, kb.disease_name, kb.scientific_name, kb.pathogen_type,
           kb.symptoms, kb.mechanical_treatment, kb.sanitation_treatment, kb.chemical_actives,
           kb.prevention,
           1 - (kb.embedding <=> query_embedding) AS similarity
       FROM knowledge_base kb
       WHERE (filter_commodity IS NULL OR LOWER(kb.commodity) = LOWER(filter_commodity))
         AND (1 - (kb.embedding <=> query_embedding)) >= match_threshold
       ORDER BY kb.embedding <=> query_embedding
       LIMIT match_count;
   END;
   $$;
   ```

#### Database Discrepancies in `laporan.md` and `schema.sql`:
1. **Missing `disease_reference_images` DDL**: Table `disease_reference_images` is actively populated by `data/upload_dataset_to_supabase.py` and queried by `database/repository.py:get_reference_image()`. However, `database/schema.sql` does NOT define `CREATE TABLE disease_reference_images`! `laporan.md` §4.6 claims running `schema.sql` creates this table, which is false until the DDL is updated.
2. **Missing `followup_notes` in `consultation_audits`**: `api/routes/admin.py:137` accepts `AdminAuditFollowUpSchema` (`followup_notes`) and attempts to update `consultation_audits`. Since `schema.sql` lacks this column, the update query will fail on a fresh schema deployment.
3. **RPC Signature Truncation**: `laporan.md` §6 only provides the inner `SELECT` statement and omits the function header, default parameter values, and return table typing.

---

### 4.3 Weather Services & Fallback Mechanisms

#### Implementation Anatomy (`services/weather_service.py`):
1. **Tier 1: WeatherAPI.com**:
   - Endpoint: `https://api.weatherapi.com/v1/forecast.json?key={api_key}&q={loc_clean}&days=1&lang=id`
   - Client timeout: 10.0 seconds.
   - Extracts: `temp_c`, `humidity`, `condition.text`, `precip_mm`, and `daily_chance_of_rain`.
2. **Tier 2: Open-Meteo API (Fallback)**:
   - Triggered when `api_key` is empty, HTTP status != 200, or network exception occurs.
   - Geocoding resolution:
     1. Dictionary of 12 known agricultural regions: Karawang, Brebes, Kediri, Malang, Bandung, Garut, Subang, Indramayu, Boyolali, Medan, Makassar, Jakarta.
     2. Open-Meteo Geocoding API (`https://geocoding-api.open-meteo.com/v1/search`) with 8.0s timeout.
     3. Ultimate default coordinate: `(-6.3060, 107.3019, "Karawang (Default Sentra Padi)")`.
   - Forecast Endpoint: `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code&hourly=precipitation_probability&timezone=Asia%2FJakarta`.
3. **Tier 3: Local Agronomic Double-Fallback**:
   - If Open-Meteo also fails or encounters a timeout, the method catches `Exception` and returns a verified safe static fallback:
     - Temperature: 29.0 °C, Humidity: 78%, Rain chance: 25%
     - Condition: "Cerah Berawan (Estimasi)"
     - Advisories: Safe morning spraying and scheduled fertilization.
4. **Advisory Rules (`_build_advisories`)**:
   - **High Rain Risk**: `precip > 0.5 mm` OR `rain_prob > 50%` $\rightarrow$ Postpone pesticide spraying (minimum 4-6 hours sunny window needed); avoid broadcasting granular fertilizers.
   - **High Humidity Risk**: `humidity > 85%` $\rightarrow$ Alert fungal spore trigger (Blas/Antracnose); require stickers/adjuvants; recommend soil drenching with Calcium/Silica.
   - **Optimal Condition**: Else $\rightarrow$ Spraying optimal at 06.30 - 09.00 or 15.30 - 17.00; fertilization safe.

---

### 4.4 Guardrails & Confidence Threshold Verification

#### Codebase Verification:
- **Configuration Parameter**: `core/config.py:36`:
  `confidence_threshold: float = Field(default=0.70, alias="CONFIDENCE_THRESHOLD")`
- **Evaluation Mechanism**: `graph_builder.py:289-291`:
  ```python
  if confidence < settings.confidence_threshold or rujuk_ppl:
      logger.info(f"Guardrail aktif: Confidence {confidence} < {settings.confidence_threshold}")
      return {"final_response": SAFE_FALLBACK_MESSAGE}
  ```
  The condition evaluates strictly as `confidence < 0.70`. Any score $\ge 0.70$ (with `rujuk_ke_ppl == False`) proceeds to formatted diagnosis.
- **Verbatim Fallback Message (`agents/prompts.py:20-29`)**:
  ```text
  🌾 *Pemberitahuan Diagnosis TaniPintar*

  Mohon maaf Bapak/Ibu Petani, berdasarkan deskripsi gejala yang disampaikan, indikasi penyakit atau hama belum dapat dipastikan secara akurat (Tingkat Keyakinan < 70%).

  ⚠️ *Demi mencegah kesalahan penanganan atau pemborosan obat*:
  1. Kami menyarankan untuk tidak langsung menyemprotkan pestisida kimiawi sembarangan.
  2. Hubungi atau temui Petugas Penyuluh Lapangan (PPL) / Dinas Pertanian di Balai Penyuluhan Pertanian (BPP) kecamatan setempat untuk inspeksi langsung.
  3. Anda juga dapat mengirimkan *foto bagian tanaman yang sakit* secara lebih dekat dan jelas (daun, batang, atau buah) agar dapat diarsipkan dan diperiksa lebih lanjut.
  ```
  *Note*: `laporan.md` §7 provides a different paraphrased Indonesian text instead of this exact system output.

---

### 4.5 Project Layout & Dependencies

#### Exact Dependency List (`requirements.txt` / `pyproject.toml`):
```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic>=2.8.0
pydantic-settings>=2.4.0
pydantic-ai>=0.0.18
langgraph>=0.2.20
langchain-core>=0.3.0
langchain-google-genai>=2.0.0
google-genai>=0.1.1
supabase>=2.6.0
httpx>=0.27.0
python-dotenv>=1.0.1
python-multipart>=0.0.9
```

#### Authoritative File Structure Alignment:
Files physically present in repository but omitted from `laporan.md` §11:
- `deploy.md` (Production deployment instructions across Docker, VPS, PaaS)
- `progres.md` (Checklist of milestones and 6 MVP features)
- `README.md` (Repository documentation)
- `.dockerignore` (Docker build exclusion rules)
- `uv.lock` (Deterministic dependency lockfile)
- `skills-lock.json` (Agent skills metadata)
- `ORIGINAL_REQUEST.md` (Project requirement specification)
- `logs/` (Application log destination directory)
- `waha_data/` (WAHA local session directory mapped in `docker-compose.yml`)

---

## 5. Comprehensive Discrepancy & Misalignment Matrix

| # | Laporan.md Location | Laporan.md Claim | Codebase Reality | Recommended Action |
|---|---------------------|------------------|------------------|--------------------|
| 1 | Line 90, 241, 317 | Plaintext API key `76d7a4136a6948e8ac464008250810` printed in diagram, table, and text | Sensitive live credential leaked | Replace all occurrences with `<WEATHER_API_KEY>` or `.env` reference |
| 2 | Lines 98-99 (Diagram 2.1) | `AuditSaver --> WAHA` & `AuditSaver -.-> MetaAPI` | `audit_saver_node` only writes to Supabase. Response is sent by `process_incoming_message` in `api/routes/whatsapp.py` | Fix Mermaid diagram flow: FastAPI Webhook calls `tani_graph_app`, then invokes `WhatsAppService` to send message |
| 3 | Lines 110-141 (Diagram 2.2) | Service nodes are nested inside `state router { ... }` | `router` is a single LangGraph node that conditionally transitions to 7 separate top-level nodes | Redraw StateGraph Mermaid diagram to accurately reflect LangGraph node structure |
| 4 | Line 269 (§4.6) | Executing `database/schema.sql` creates `disease_reference_images` | `schema.sql` does NOT contain `CREATE TABLE disease_reference_images` | Clarify in report and document the missing table DDL (or add it to schema) |
| 5 | Line 349 (§5.8) | PPL can update follow-up notes on consultations | `consultation_audits` in `schema.sql` has no `followup_notes` column | Add `followup_notes TEXT` to table schema documentation |
| 6 | Lines 371-383 (§6) | Shows partial `SELECT` query without `CREATE FUNCTION` header | `schema.sql` has full RPC signature with 4 parameters and table return | Update with complete `CREATE OR REPLACE FUNCTION match_knowledge (...)` |
| 7 | Lines 393-394 (§7) | Paraphrased fallback message text | Exact text defined in `agents/prompts.py:SAFE_FALLBACK_MESSAGE` | Align quote with actual `SAFE_FALLBACK_MESSAGE` |
| 8 | Lines 10, 65, 159, 222 | Mentions "Google Gemini 3.5 Flash" | While `GEMINI_MODEL=gemini-3.5-flash` is configured in `.env`/`config.py`, candidate models in `diagnosis_agent.py` are `["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.8-flash"]`, and `.env.example` specifies `gemini-1.5-flash` | Clarify model configuration and compatibility |
| 9 | Line 294 (§5.1) | Padi stem borer scientific name written as *Scirpophaga innotata* | `data/knowledge/padi_diseases.json` uses *Scirpophaga incertulas* | Align scientific name to *Scirpophaga incertulas* (or note both species) |
| 10 | Lines 504-557 (§11) | Directory tree omits `deploy.md`, `progres.md`, `README.md`, `.dockerignore`, `uv.lock`, `logs/`, `waha_data/` | Files and folders exist in the workspace | Update directory tree to be 100% faithful to repository files |
