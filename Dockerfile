FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    SNAPSHOT_INTERVAL_SEC=0

EXPOSE 5000
CMD ["python", "app.py"]


