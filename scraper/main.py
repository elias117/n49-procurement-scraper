import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scraper")

if __name__ == "__main__":
    logger.info("Scraper container started (Phase 1 stub)")
    logger.info("Scraper pipeline will be implemented in Phase 2")
    # Keep container running so Docker Compose doesn't restart it
    while True:
        time.sleep(3600)
