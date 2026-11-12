FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend:/app/tools:/app
ENV SOFTWARE_PROVENANCE_FILE=/app/software_provenance.json

COPY pyproject.toml ./
COPY backend ./backend
COPY tools ./tools
COPY development ./development
COPY .git /tmp/git-meta

RUN python backend/experiments/software_provenance.py --write-stamp /app/software_provenance.json --git-dir /tmp/git-meta \
    && rm -rf /tmp/git-meta

RUN pip install --no-cache-dir ".[test]"

CMD ["pytest"]
