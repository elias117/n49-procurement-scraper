ALTER TABLE listings
ADD COLUMN reference_number VARCHAR(500);

CREATE INDEX listings_reference_number_idx ON listings(reference_number);
