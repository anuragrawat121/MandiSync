# Hugging Face Spaces — API + daily ingest in one container.
# Railway still uses Backend/Dockerfile.

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY Backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Backend/ .

ENV PYTHONUNBUFFERED=1
ENV SKIP_DB_INIT_ON_IMPORT=true
ENV PYTHONPATH=/app
ENV PORT=7860
ENV RUN_INGEST_LOOP=true
ENV DB_WAIT_SECONDS=180

EXPOSE 7860

CMD ["python", "scripts/entrypoint.py"]
