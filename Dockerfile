FROM docker.io/library/python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 opsatlas \
    && useradd --uid 10001 --gid 10001 --no-create-home opsatlas \
    && mkdir -p /app/data /app/docs \
    && chown -R 10001:10001 /app/data
COPY app ./app
COPY scripts ./scripts
USER 10001:10001
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:create_app","--factory","--host","0.0.0.0","--port","8000"]
