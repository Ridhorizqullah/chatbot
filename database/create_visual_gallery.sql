-- =====================================================================
-- TANIPINTAR: DDL & SECURITY SETUP UNTUK VISUAL RAG PGVECTOR
-- Jalankan skrip ini di SQL Editor Supabase Dashboard Anda.
-- =====================================================================

-- 1. Pastikan ekstensi vector aktif
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Buat tabel disease_image_gallery
CREATE TABLE IF NOT EXISTS public.disease_image_gallery (
    id VARCHAR(120) PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    disease_name VARCHAR(150) NOT NULL,
    scientific_name VARCHAR(150),
    commodity VARCHAR(50) DEFAULT 'cabai',
    organ VARCHAR(50) NOT NULL, -- 'buah', 'daun', 'tanaman_utuh'
    filename VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    storage_public_url TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL, -- 768-dim Visual Vector (gemini-embedding-2)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Aktifkan Row-Level Security (RLS) sesuai panduan resmi Supabase
ALTER TABLE public.disease_image_gallery ENABLE ROW LEVEL SECURITY;

-- Policy SELECT untuk publik (anon & authenticated) agar bot dan web bisa membaca referensi
DROP POLICY IF EXISTS "Public read access for disease image gallery" ON public.disease_image_gallery;
CREATE POLICY "Public read access for disease image gallery" 
ON public.disease_image_gallery 
FOR SELECT 
TO anon, authenticated
USING (true);

-- Policy INSERT/UPDATE khusus service_role (Admin & Ingestion Script)
DROP POLICY IF EXISTS "Service role write access for disease image gallery" ON public.disease_image_gallery;
CREATE POLICY "Service role write access for disease image gallery" 
ON public.disease_image_gallery 
FOR ALL 
TO service_role 
USING (true)
WITH CHECK (true);

-- 4. Indeks IVFFlat untuk pencarian kemiripan kosinus ultra-cepat (< 30ms)
CREATE INDEX IF NOT EXISTS idx_disease_image_gallery_embedding 
ON public.disease_image_gallery 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 10);

-- Indeks B-Tree untuk filter organ dan komoditas
CREATE INDEX IF NOT EXISTS idx_disease_image_gallery_organ 
ON public.disease_image_gallery(organ, commodity);

-- 5. Stored Procedure RPC untuk Image-to-Image Vector Cosine Similarity Search
CREATE OR REPLACE FUNCTION public.match_disease_images (
    query_image_embedding VECTOR(768),
    match_threshold FLOAT DEFAULT 0.65,
    match_count INT DEFAULT 3,
    filter_organ TEXT DEFAULT NULL
)
RETURNS TABLE (
    id VARCHAR(120),
    disease_name VARCHAR(150),
    scientific_name VARCHAR(150),
    organ VARCHAR(50),
    storage_public_url TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
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
    FROM public.disease_image_gallery g
    WHERE (filter_organ IS NULL OR LOWER(g.organ) = LOWER(filter_organ))
      AND (1 - (g.embedding <=> query_image_embedding)) >= match_threshold
    ORDER BY g.embedding <=> query_image_embedding
    LIMIT match_count;
END;
$$;

-- Berikan izin eksekusi RPC ke anon dan authenticated
GRANT EXECUTE ON FUNCTION public.match_disease_images(VECTOR(768), FLOAT, INT, TEXT) TO anon, authenticated, service_role;
