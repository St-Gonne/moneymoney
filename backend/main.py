"""
MoneyMoney Family Portfolio Backend Service (Cloud Run / FastAPI)
Unified production entrypoint exposing the fail-closed 4-gate statement ingestion pipeline,
canonical ledger queries, FIFO tax lot accounting, and AMFI EOD NAV sync.
"""
import os
from app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
