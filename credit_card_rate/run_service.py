"""
Simple script to run the Card Rates Service
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "card_rates_service:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )

