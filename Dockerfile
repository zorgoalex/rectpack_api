FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PORT=8080 \
    LOG_LEVEL=info \
    MAX_BODY_BYTES=5242880 \
    MAX_INSTANCES=5000 \
    DEFAULT_TIME_LIMIT_MS=800 \
    DEFAULT_RESTARTS=5 \
    MAX_CONCURRENT_JOBS=1 \
    DEFAULT_UNIT_SCALE=100

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD python -c "import os,sys,urllib.request;port=os.getenv('PORT','8080');url='http://127.0.0.1:%s/health/live'%port;resp=urllib.request.urlopen(url,timeout=2);sys.exit(0 if resp.status==200 else 1)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
