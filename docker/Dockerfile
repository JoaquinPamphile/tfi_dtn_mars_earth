FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/backend

COPY pyproject.toml ./
COPY backend ./backend

RUN pip install --no-cache-dir ".[test]"

CMD ["pytest"]
