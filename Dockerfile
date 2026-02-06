FROM python:3.11-slim

# System dependencies for ping & traceroute
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    traceroute \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY config.py main.py monitor.py ui.py alerts.py pinger.py \
     stats_repository.py problem_analyzer.py route_analyzer.py ./
COPY services/ ./services/
COPY infrastructure/ ./infrastructure/
COPY pinger/ ./pinger/

# Create data directories
RUN mkdir -p /app/logs /app/traceroutes

# Environment
ENV PYTHONUNBUFFERED=1
ENV ENABLE_METRICS=true
ENV METRICS_ADDR=0.0.0.0
ENV METRICS_PORT=8000
ENV ENABLE_HEALTH_ENDPOINT=true
ENV HEALTH_ADDR=0.0.0.0
ENV HEALTH_PORT=8001

# Expose metrics and health ports
EXPOSE 8000 8001

CMD ["python", "pinger.py"]
