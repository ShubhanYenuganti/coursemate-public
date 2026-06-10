-- Add token_count column to material_page_text for retrieval budget accounting.
-- Used by the PageIndex retrieval budget frontier to admit raw pages by stored token cost.
ALTER TABLE material_page_text
ADD COLUMN IF NOT EXISTS token_count INTEGER;
