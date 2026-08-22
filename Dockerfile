FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BIOS_RUNTIME_DIR=/app/runtime \
    BIOS_MODE=authoring \
    ENABLE_SOURCE_POLLING=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 berry \
    && useradd --uid 1000 --gid berry --create-home --shell /usr/sbin/nologin berry

WORKDIR /app

COPY requirements-web.txt /app/requirements-web.txt
RUN pip install --no-cache-dir -r /app/requirements-web.txt

COPY app /app/app
COPY schemas /app/schemas
COPY scripts /app/scripts
COPY benchmarks /app/benchmarks
COPY data /app/seed/data
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/runtime/data /app/runtime/inbox \
    && chown -R berry:berry /app

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
