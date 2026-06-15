# Multi-stage build for the generator webapp.
# nixpacks baked the full build toolchain + -dev headers + nix store into the
# final image (~2.7 GB). Here the compile stage stays separate and the runtime
# image carries only the cairo runtime libs + installed Python packages.

# ---- builder: compile pycairo / noise against the -dev headers ----
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc python3-dev libcairo2-dev pkg-config libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-railway.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-railway.txt

# ---- runtime: slim base + cairo runtime lib only ----
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

ENV PORT=8080
# Mirrors Procfile (Railway uses this CMD for Docker builds, not the Procfile).
CMD ["sh", "-c", "gunicorn generator:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 60 --max-requests 200 --max-requests-jitter 50 --access-logfile - --error-logfile - --capture-output --preload"]
