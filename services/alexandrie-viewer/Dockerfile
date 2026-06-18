FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask gunicorn google-cloud-storage

COPY app.py .

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 120 app:app
