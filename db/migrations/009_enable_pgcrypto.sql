-- Enable pgcrypto for crypt() password verification in API auth endpoints
CREATE EXTENSION IF NOT EXISTS pgcrypto;
