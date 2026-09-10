from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import approvals, orders, tna

app = FastAPI(
    title="Merch Ops API",
    description="Order status assessment + TNA deadline watching, multi-tenant SaaS backend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orders.router)
app.include_router(tna.router)
app.include_router(approvals.router)


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}
