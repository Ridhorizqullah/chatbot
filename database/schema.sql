-- =====================================================================
-- TANIPINTAR BOT: SUPABASE DATABASE INITIALIZATION DDL
-- Jalankan skrip ini di SQL Editor dashboard Supabase Anda.
-- =====================================================================

-- 1. Aktifkan ekstensi vector untuk RAG Semantik
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tabel Knowledge Base Pertanian (Cabai & Padi)
CREATE TABLE IF NOT EXISTS knowledge_base (
    id BIGSERIAL PRIMARY KEY,
    commodity VARCHAR(50) NOT NULL, -- 'cabai' atau 'padi'
    disease_name VARCHAR(150) NOT NULL,
    scientific_name VARCHAR(150),
    pathogen_type VARCHAR(50) NOT NULL, -- 'Jamur', 'Bakteri', 'Virus', 'Hama'
    symptoms TEXT NOT NULL,
    mechanical_treatment TEXT NOT NULL,
    sanitation_treatment TEXT NOT NULL,
    chemical_actives TEXT,
    prevention TEXT,
    embedding VECTOR(768), -- Sesuai dimensi embedding Google text-embedding-004
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Index IVFFlat untuk performa query kemiripan kosinus cepat
CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx
ON knowledge_base
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 3. Fungsi RPC untuk Pencarian Kesamaan Cosine (Semantic Search)
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
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE (filter_commodity IS NULL OR LOWER(kb.commodity) = LOWER(filter_commodity))
      AND (1 - (kb.embedding <=> query_embedding)) >= match_threshold
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 4. Tabel Sesi Percakapan Petani (LangGraph Memory Persistence)
CREATE TABLE IF NOT EXISTS chat_sessions (
    phone_number VARCHAR(30) PRIMARY KEY,
    current_state JSONB DEFAULT '{}'::jsonb,
    last_crop_context VARCHAR(50),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. Tabel Rekam Jejak Konsultasi & Audit PPL
CREATE TABLE IF NOT EXISTS consultation_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(30) NOT NULL,
    crop_type VARCHAR(50),
    suspected_disease VARCHAR(150),
    confidence_score FLOAT NOT NULL,
    is_referred_to_ppl BOOLEAN DEFAULT FALSE,
    media_url TEXT, -- URL file bukti gejala di Supabase Storage
    farmer_query TEXT NOT NULL,
    bot_recommendation JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Index untuk filter cepat nomor telepon dan tanggal audit
CREATE INDEX IF NOT EXISTS idx_consultation_phone ON consultation_audits(phone_number);
CREATE INDEX IF NOT EXISTS idx_consultation_created_at ON consultation_audits(created_at DESC);

-- 6. Tabel Harga Pasar Komoditas Padi & Cabai Se-Indonesia (Otomatis & Admin)
CREATE TABLE IF NOT EXISTS market_prices (
    id BIGSERIAL PRIMARY KEY,
    price_date DATE NOT NULL,
    commodity VARCHAR(100) NOT NULL, -- 'Cabai Rawit Merah', 'Cabai Merah Keriting', 'Gabah Kering Panen', 'Beras Medium'
    province VARCHAR(100) NOT NULL,  -- 'Jawa Barat', 'Jawa Timur', 'Jawa Tengah', 'Sumatera Utara', 'Nasional', dll.
    farmgate_price INT NOT NULL,     -- Harga di tingkat petani (Rp/kg)
    consumer_price INT NOT NULL,     -- Harga di tingkat pasar/konsumen (Rp/kg)
    unit VARCHAR(20) DEFAULT 'kg',
    source VARCHAR(100) DEFAULT 'Sistem Otomatis / Admin',
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    CONSTRAINT unique_price_entry UNIQUE (price_date, commodity, province)
);

CREATE INDEX IF NOT EXISTS idx_market_prices_lookup ON market_prices(commodity, province, price_date DESC);

