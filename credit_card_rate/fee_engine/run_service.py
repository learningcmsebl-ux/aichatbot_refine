"""
Run Fee Engine Service
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("FEE_ENGINE_PORT", "8003"))
    host = os.getenv("FEE_ENGINE_HOST", "0.0.0.0")
    
    print(f"Starting Fee Engine Service on {host}:{port}")
    print(f"Database: {os.getenv('FEE_ENGINE_DB_URL', 'Using POSTGRES_* env vars')}")
    
    uvicorn.run(
        "fee_engine_service:app",
        host=host,
        port=port,
        reload=os.getenv("FEE_ENGINE_RELOAD", "false").lower() == "true"
    )
