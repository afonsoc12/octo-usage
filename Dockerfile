# Multi-stage build for slim image
FROM python:3.14-alpine AS builder

WORKDIR /tmp

# Install uv for fast dependency resolution
RUN apk add --no-cache curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    rm -rf /root/.cache

ENV PATH="/root/.local/bin:$PATH"

# Exclude dev dependencies during install
ENV UV_NO_DEV=1

# Copy project files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv && \
    uv pip install --python /opt/venv/bin/python .

# Runtime stage
FROM python:3.14-alpine

ARG USER=coolio
ARG GROUP=coolio
ARG UID=1234
ARG GID=4321

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install minimal runtime dependencies
RUN apk add --no-cache tzdata

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code to /app
COPY octo_usage /app/octo_usage

# Create non-root user
RUN addgroup --gid $GID $GROUP && \
    adduser -D -H --gecos "" \
                   --ingroup "$GROUP" \
                   --uid "$UID" \
                   "$USER" && \
    chown -R $USER:$GROUP /app

USER $USER

ENTRYPOINT ["python", "-m", "octo_usage"]
CMD ["--help"]
