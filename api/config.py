"""API service configuration. Loads from environment variables."""
import os
import logging

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required.")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"

# RRF parameter (k=60 is the original paper default; configurable for tuning)
RRF_K = int(os.environ.get("RRF_K", "60"))

# Oversampling: fetch this many candidates from each sub-query before RRF merge
RRF_OVERSAMPLE_FACTOR = int(os.environ.get("RRF_OVERSAMPLE_FACTOR", "4"))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("api")

if not OPENAI_API_KEY:
    logger.warning(
        "OPENAI_API_KEY is not set; semantic search embeddings will be disabled."
    )
