-- =====================================================================
-- TANIPINTAR BOT: SUPABASE PATCH / PERBAIKAN SCHEMA & RPC
-- Jalankan skrip SQL ini di SQL Editor dashboard Supabase Anda.
-- =====================================================================

-- 1. Pastikan ekstensi vector aktif di schema extensions
CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;

-- 2. Buat view kompatibilitas user_sessions jika belum ada
--    (Menghubungkan tabel user_sessions ke chat_sessions)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename = 'user_sessions') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_views WHERE schemaname = 'public' AND viewname = 'user_sessions') THEN
            CREATE VIEW public.user_sessions AS SELECT * FROM public.chat_sessions;
        END IF;
    END IF;
END $$;

-- 3. Perbaiki Fungsi RPC match_knowledge
--    KUNCI: Menambahkan 'SET search_path = public, extensions' agar
--    operator '<=>' dari pgvector dapat ditemukan tanpa error 42883.
CREATE OR REPLACE FUNCTION match_knowledge (
    query_embedding extensions.vector(768),
    match_threshold FLOAT DEFAULT 0.50,
    match_count INT DEFAULT 3,
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
SET search_path = public, extensions
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.commodity,
        kb.disease_name,
        kb.scientific_name,
        kb.pathogen_type,
        kb.symptoms,
        kb.mechanical_treatment,
        kb.sanitation_treatment,
        kb.chemical_actives,
        kb.prevention,
        (1 - (kb.embedding <=> query_embedding))::FLOAT AS similarity
    FROM knowledge_base kb
    WHERE (filter_commodity IS NULL OR LOWER(kb.commodity) = LOWER(filter_commodity))
      AND (1 - (kb.embedding <=> query_embedding)) >= match_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 4. Perbaiki Fungsi RPC match_disease_images (Visual RAG)
CREATE OR REPLACE FUNCTION match_disease_images (
    query_image_embedding extensions.vector(768),
    match_threshold FLOAT DEFAULT 0.65,
    match_count INT DEFAULT 3,
    filter_organ TEXT DEFAULT NULL
)
RETURNS TABLE (
    id VARCHAR(100),
    disease_name VARCHAR(150),
    scientific_name VARCHAR(150),
    organ VARCHAR(50),
    storage_public_url TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SET search_path = public, extensions
AS $$
BEGIN
    RETURN QUERY
    SELECT
        g.id,
        g.disease_name,
        g.scientific_name,
        g.organ,
        g.storage_public_url,
        (1 - (g.embedding <=> query_image_embedding))::FLOAT AS similarity
    FROM disease_image_gallery g
    WHERE (filter_organ IS NULL OR LOWER(g.organ) = LOWER(filter_organ))
      AND (1 - (g.embedding <=> query_image_embedding)) >= match_threshold
    ORDER BY g.embedding <=> query_image_embedding
    LIMIT match_count;
END;
$$;
