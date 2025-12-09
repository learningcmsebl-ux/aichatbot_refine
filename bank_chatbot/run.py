"""
Simple script to run the Bank Chatbot application
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,  # Enable auto-reload in development
        log_level="info"
    )

