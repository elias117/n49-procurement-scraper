FROM mcr.microsoft.com/playwright/python:v1.51.0-noble

WORKDIR /app

# Install Xvfb for non-headless Chromium in Docker
# POC confirmed: headless=True gets 403-blocked by procurement portals
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*

# Build context is project root (not ./scraper), so files land at /app/scraper/
# and package-qualified imports (from scraper.config import ...) resolve correctly.
COPY scraper/requirements.txt ./scraper/
RUN pip install --no-cache-dir -r scraper/requirements.txt

# Ensure Chromium is installed (may already be in base image)
RUN python -m playwright install chromium

COPY scraper/ ./scraper/

# Run scraper with Xvfb virtual framebuffer
# Chromium runs in non-headless mode inside the virtual display
CMD ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "python", "scraper/main.py"]
