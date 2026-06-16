FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY worker ./worker

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=whispr.settings

CMD ["python", "worker/run.py"]
