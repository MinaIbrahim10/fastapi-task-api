FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

RUN groupadd --system app \
 && useradd --system --gid app --create-home app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

COPY main.py postgres_repository.py redis_client.py ./
COPY sql ./sql

RUN chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
