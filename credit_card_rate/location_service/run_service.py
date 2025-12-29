"""
Run Location Service
"""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("LOCATION_SERVICE_PORT", "8004"))
    host = os.getenv("LOCATION_SERVICE_HOST", "0.0.0.0")
    
    print(f"Starting Location Service on {host}:{port}")
    print(f"Database: {os.getenv('LOCATION_SERVICE_DB_URL', 'Using POSTGRES_* env vars')}")
    
    uvicorn.run(
        "location_service:app",
        host=host,
        port=port,
        reload=os.getenv("LOCATION_SERVICE_RELOAD", "false").lower() == "true"
    )

