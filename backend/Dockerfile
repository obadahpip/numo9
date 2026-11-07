# syntax=docker/dockerfile:1.7
# Numo9 backend image. Build context: backend/
#   docker build --target dev     -t numo9-backend:dev .
#   docker build --target runtime -t numo9-backend .

ARG PYTHON_IMAGE=python:3.12.16-slim-bookworm

# ---- base: shared OS layer ---------------------------------------------------
FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH
WORKDIR /app

# ---- builder: runtime dependencies into a venv --------------------------------
FROM base AS builder
RUN python -m venv /opt/venv
COPY requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

# ---- dev: + dev/test dependencies, source bind-mounted by compose -------------
FROM builder AS dev
COPY requirements/dev.txt requirements/dev.txt
RUN pip install -r requirements/dev.txt
COPY . .
ENV DJANGO_SETTINGS_MODULE=numo9.settings.dev
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"]

# ---- runtime: minimal production image, non-root ------------------------------
FROM base AS runtime
RUN groupadd --system --gid 10001 numo9 \
    && useradd --system --uid 10001 --gid numo9 --home-dir /app --shell /usr/sbin/nologin numo9
COPY --from=builder /opt/venv /opt/venv
COPY --chown=numo9:numo9 . .
USER numo9
ENV DJANGO_SETTINGS_MODULE=numo9.settings.prod
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"
CMD ["gunicorn", "numo9.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
