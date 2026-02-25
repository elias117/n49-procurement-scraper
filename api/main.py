"""FastAPI application entry point."""
from fastapi import FastAPI
from api.routers import health, listings, portal_health, search, users

app = FastAPI(
    title="Procurement Intelligence API",
    description="Hybrid search API for Canadian procurement listings",
    version="0.1.0",
    root_path="/api",  # nginx strips /api/ prefix via proxy_pass
)

app.include_router(health.router)
app.include_router(search.router)
app.include_router(listings.router)
app.include_router(portal_health.router)
app.include_router(users.router)
