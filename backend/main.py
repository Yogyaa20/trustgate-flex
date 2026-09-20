"""
TrustGate Flex — FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import traceback
import logging

from backend.api.routes import access, alerts, appeals, approvals, audit, auth, debug, assets, devices, users
from backend.db.database import create_all_tables, SessionLocal
from backend.models.models import User, Base
from backend.db.database import engine

logger = logging.getLogger(__name__)

app = FastAPI(
    title="TrustGate Flex API",
    description="Explainable Just-In-Time Access Gateway",
    version="1.0.0",
)

# ── CORS Middleware ─────────────────────────────────────
# Allow Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup Event ───────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """Ensure database tables are created on startup."""
    create_all_tables()
    
    db = SessionLocal()
    try:
        tables_count = len(Base.metadata.tables)
        users_count = db.query(User).count()
        print("✓ Database connected")
        print(f"✓ {tables_count} tables found")
        print(f"✓ {users_count} users seeded")
        print("✓ All routes registered")
        print("→ TrustGate Flex API ready at http://localhost:8000")
        print("→ API docs at http://localhost:8000/docs")
    except Exception as e:
        print(f"Startup check failed: {e}")
    finally:
        db.close()


# ── Health Check ────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    return {
        "status": "ok",
        "service": "TrustGate Flex",
        "version": "1.0.0",
    }


# ── Route Registration ──────────────────────────────────
# Prefix all API routes with /api/v1
api_prefix = "/api/v1"

app.include_router(auth.router, prefix=api_prefix)
app.include_router(access.router, prefix=api_prefix)
app.include_router(approvals.router, prefix=api_prefix)
app.include_router(alerts.router, prefix=api_prefix)
app.include_router(audit.router, prefix=api_prefix)
app.include_router(appeals.router, prefix=api_prefix)
app.include_router(assets.router, prefix=api_prefix)
app.include_router(devices.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(debug.router, prefix="/debug", tags=["debug"])

@app.post("/demo/reset", tags=["system"])
def demo_reset():
    import subprocess
    import sys
    try:
        result = subprocess.run(
            [sys.executable, "scripts/seed_db.py", "--reset"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"status": "reset", "message": "Demo data reset successfully"}
        else:
            return {"status": "error", "message": result.stderr}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
