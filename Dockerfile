FROM python:3.11-slim

# System deps for WeasyPrint PDF generation + curl for ECS healthchecks
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Set python path
ENV PYTHONPATH=/app
ENV ENV=LOCAL
