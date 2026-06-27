# Stage 1: Build dependencies using Python 3.12 on Alpine (highly secure and minimal size)
FROM python:3.12-alpine AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Upgrade pip to the latest secure version and install compile tools
RUN apk update && \
    apk upgrade --no-cache && \
    pip install --no-cache-dir --upgrade pip && \
    apk add --no-cache build-base gcc musl-dev libffi-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final minimal runtime image
FROM python:3.12-alpine AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/automation/.local/bin:$PATH \
    FLASK_APP=app/main.py

# Security Hardening: Upgrade Alpine packages to patch CVEs (like CVE-2026-34743 in xz-libs) 
# and upgrade pip to patch python-pkg CVEs (like CVE-2025-8869, CVE-2026-3219, CVE-2026-6357, CVE-2026-1703)
RUN apk update && \
    apk upgrade --no-cache && \
    pip install --no-cache-dir --upgrade pip

# Create a non-privileged system user and group in Alpine
RUN addgroup -g 10001 -S automation && \
    adduser -u 10001 -S -G automation -h /home/automation -s /bin/sh automation

# Copy installed Python packages from builder stage with correct non-root ownership
COPY --from=builder --chown=automation:automation /root/.local /home/automation/.local
COPY --chown=automation:automation app/ /app/app/
COPY --chown=automation:automation config/ /app/config/

# Ensure ownership of log/config directories
RUN mkdir -p /app/logs && chown -R automation:automation /app/logs

USER automation

EXPOSE 8000

CMD ["gunicorn", "-w", "4", "--threads", "4", "-b", "0.0.0.0:8000", "app.main:app"]
