from fastapi import FastAPI
from app.api.price_estimate import router as price_router
from app.database import init_db

app = FastAPI(
    title="Price Estimate API",
    version="2.0.0",
    description="Per-part INR repair/replacement cost estimates for Autoclaim.",
)

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(price_router)

@app.get("/")
def root():
    return {"status": "Price API running", "port": 8001, "version": "2.0.0"}
