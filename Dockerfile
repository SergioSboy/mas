FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/results \
    && chown app:app /app/results

COPY main.py init_db.py ./
COPY salesbench/ ./salesbench/
COPY tests/ ./tests/

USER app
ENTRYPOINT ["python", "main.py"]
CMD ["--backend", "demo"]
