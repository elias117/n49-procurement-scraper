FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt ./api/
RUN pip install --no-cache-dir -r api/requirements.txt

COPY api/ ./api/
COPY db/ ./db/

# Run with uvicorn; host 0.0.0.0 so Docker networking works
# Build context is project root (not ./api), so files land at /app/api/
# and package-qualified imports (from api import config) resolve correctly.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
