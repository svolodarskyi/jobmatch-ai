FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# Copy only the package manifest so this layer is cached unless dependencies change.
# Source code is bind-mounted at runtime — no COPY . . here.
COPY pyproject.toml ./

# pip install -e requires the package directory to exist at install time.
# The real source is bind-mounted over this stub at runtime via docker-compose.
RUN mkdir -p app && touch app/__init__.py

# Install an editable package so `import app` works when the source is
# mounted in at /app via docker-compose volume.
RUN pip install --no-cache-dir -e ".[dev]"

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
