FROM python:3.12-slim

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
    stats_repository.py problem_analyzer.py route_analyzer.py \
    single_instance.py single_instance_notifications.py \
    ./
COPY config/ ./config/
COPY core/ ./core/
COPY services/ ./services/
COPY infrastructure/ ./infrastructure/
COPY pinger/ ./pinger/
COPY ui_protocols/ ./ui_protocols/


# Copy healthcheck script
COPY scripts/healthcheck.py /app/healthcheck.py
RUN chmod +x /app/healthcheck.py

# Create data directories
RUN mkdir -p /app/logs /app/traceroutes

# Create non-root user
RUN useradd -m -u 1000 pinger && chown -R pinger:pinger /app
USER pinger

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENABLE_METRICS=true
ENV METRICS_ADDR=0.0.0.0
ENV METRICS_PORT=8000
ENV ENABLE_HEALTH_ENDPOINT=true
# For Kubernetes/internal network: uncomment next line
# ARG HEALTH_ADDR_OVERRIDE
ENV HEALTH_ADDR=0.0.0.0
ENV HEALTH_PORT=8001

# Expose metrics and health ports
EXPOSE 8000 8001

# Health check (handles optional basic auth via env vars)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python /app/healthcheck.py || exit 1

ENTRYPOINT ["python", "-m", "pinger"]
CMD []
