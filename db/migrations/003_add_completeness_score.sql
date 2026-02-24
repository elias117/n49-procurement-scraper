-- Add completeness_score column for tracking field population per listing
ALTER TABLE listings ADD COLUMN IF NOT EXISTS completeness_score NUMERIC DEFAULT 0;
CREATE INDEX IF NOT EXISTS listings_completeness_idx ON listings (completeness_score);
