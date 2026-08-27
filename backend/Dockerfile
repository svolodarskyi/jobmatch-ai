FROM python:3.11-slim

WORKDIR /app

# Copy only the package manifest so this layer is cached unless dependencies change.
# Source code is bind-mounted at runtime — no COPY . . here.
COPY pyproject.toml ./

# Install an editable package so `import app` works when the source is
# mounted in at /app via docker-compose volume.
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
