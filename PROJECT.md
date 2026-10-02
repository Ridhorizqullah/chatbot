# Project: TaniPintar Bot Technical Report Review & Refinement

## Architecture
- **Target Document**: `E:\wa bot longchain\laporan.md` (Technical Report of TaniPintar WhatsApp Bot)
- **Reference Codebase**: `agents/`, `api/`, `core/`, `database/`, `services/`, `data/`, `tests/`, `graph_builder.py`, `main.py`, `.env.example`
- **Orchestration Model**: Multi-Agent Dispatch with Forensic Integrity Verification and Dual-Track Verification

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | R1.1 Purge Plaintext WeatherAPI Key | Remove active key `76d7a4136a6948e8ac464008250810` from lines 90, 241, 317 in `laporan.md`; replace with `<WEATHER_API_KEY>` or `.env` reference | M1 | explorer_survey_security & spec_miner |
| 2 | R1.2 WhatsApp Phone Number Masking | Mask active WhatsApp bot number `62895418133345` on line 16 to `+62 895-4181-XXXX` | M1 | explorer_survey_security |
| 3 | R1.3 Local File URI Removal | Strip `file:///e:/wa%20bot%20longchain/...` links on lines 211, 233, 269 to relative paths | M1 | explorer_survey_security |
| 4 | R1.4 Environment Configuration Security Callouts | Add GFM `[!WARNING]` security callouts and update `.env.example` with missing `WEATHER_API_KEY` & `ADMIN_API_KEY` | M1 | explorer_survey_security |
| 5 | R2.1 LangGraph StateGraph Architecture Alignment | Correct StateGraph flow in text & diagrams: `audit_saver` saves to Supabase and routes to `END`; message dispatch handled asynchronously by `process_incoming_message` in `whatsapp.py` | M2 | spec_miner_architecture |
| 6 | R2.2 Database Schema & RPC Alignment | Document full Supabase schema including `disease_reference_images` table DDL, `followup_notes` column in `consultation_audits`, and exact `match_knowledge` RPC signature | M2 | spec_miner_architecture |
| 7 | R2.3 Weather 3-Tier Multi-Provider Fallback | Document the real 3-tier architecture: Tier 1 WeatherAPI (10s timeout) -> Tier 2 Open-Meteo with 2-tier geocoding -> Tier 3 static agronomic fallback | M2 | spec_miner_architecture |
| 8 | R2.4 Guardrail Confidence Threshold & Safe Fallback | Accurately specify `< 0.70` threshold, out-of-scope commodity handling, and verbatim `SAFE_FALLBACK_MESSAGE` | M2 | spec_miner_architecture |
| 9 | R2.5 Directory Tree & Dependencies Alignment | Synchronize project directory tree in §11 and align all 13 dependencies with `requirements.txt` and `pyproject.toml` | M2 | spec_miner_architecture |
| 10 | R3.1 Mermaid Diagram 2.1 (Architecture Flow) Fix | Fix unescaped `<`, sanitize API key, remove compound subgraph edge, add Open-Meteo fallback | M3 | explorer_survey_formatting |
| 11 | R3.2 Mermaid Diagram 2.2 (StateGraph Lifecycle) Fix | Remove illegal `->` operator inside descriptions, fix unescaped `<`, restructure as valid choice-node state diagram | M3 | explorer_survey_formatting |
| 12 | R3.3 Botanical & Plant Pathological Nomenclature Italicization | Consistently italicize all binomial scientific names (*Capsicum annuum*, *Oryza sativa*, *Colletotrichum capsici*, *Magnaporthe oryzae*, *Ralstonia solanacearum*, *Begomovirus* PepYLCV, *Scirpophaga innotata* / *incertulas*, etc.) | M3 | explorer_survey_formatting |
| 13 | R3.4 GitHub Flavored Markdown Alerts Integration | Strategically embed `[!NOTE]`, `[!IMPORTANT]`, `[!TIP]`, and `[!WARNING]` throughout report sections | M3 | explorer_survey_formatting |
| 14 | R3.5 3 Pilar PHT & PPL Referral Closed-Loop Sequence | Document 3 Pilar PHT (Mekanis, Sanitasi, Kimiawi Terdaftar) and create dedicated Mermaid sequence diagram for PPL referral loop | M3 | explorer_survey_formatting |
| 15 | R4.1 Multi-Agent Review & Challenge Verification | Reviewers and Challengers independently verify rendered markdown, diagram syntax, factual consistency, and security | M4 | orchestrator procedure |
| 16 | R4.2 Forensic Integrity Audit | Independent Forensic Auditor conducts deep static and integrity analysis for zero-tolerance compliance | M4 | orchestrator procedure |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Survey & Scope Mapping | 3 parallel Explorers to catalog all gaps across R1, R2, R3 | none | DONE |
| M1 | Credential & Security Sanitization (R1) | Purge plaintext keys, mask phone, clean URIs, add env guidance in `laporan.md` and `.env.example` | M0 | DONE |
| M2 | Technical Accuracy & Architecture Alignment (R2) | Align LangGraph StateGraph, database schemas, pgvector RPC, weather fallback, guardrail threshold, directory tree | M1 | DONE |
| M3 | Typography, Formatting, Alerts & Mermaid Syntax (R3) | Fix Mermaid blocks, format GFM alerts, italicize scientific names, add 3 Pilar PHT & PPL sequence diagram | M2 | DONE |
| M4 | Comprehensive Verification & Forensic Integrity Audit | Multi-agent review (2 Reviewers, 2 Challengers, 1 Forensic Auditor) and gating verification | M3 | DONE |

## Interface Contracts
- **Document Boundary**: Modifications are applied to `laporan.md` and `.env.example`.
- **Markdown Specification**: GitHub Flavored Markdown (GFM) with UTF-8 encoding.
- **Mermaid Compatibility**: Strict Mermaid v10+ syntax compatible with standard GitHub / VS Code renderers (no unescaped `<`, no illegal `->` in state descriptions, quoted labels).
- **Environment Standards**: All credentials referenced via `<VARIABLE_NAME>` or `.env`.

## Code Layout
- Target Document: `E:\wa bot longchain\laporan.md`
- Configuration Template: `E:\wa bot longchain\.env.example`
- State & Artifacts: `E:\wa bot longchain\.agents\teamwork\`
