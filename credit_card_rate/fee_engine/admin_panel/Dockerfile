FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY fee_engine/admin_panel/requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Copy admin panel code
COPY fee_engine/admin_panel /app/admin_panel
COPY fee_engine/fee_engine_service.py /app/fee_engine_service.py

# Copy location service (if it exists at project root)
COPY location_service /app/location_service

# Expose port
EXPOSE 8009

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8009/api/health', timeout=5)" || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "admin_panel.admin_api:app", "--host", "0.0.0.0", "--port", "8009"]

