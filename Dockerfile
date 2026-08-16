FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ORIÓN backend: Digital Twin API (FastAPI). The Mission Control UI
# (orion-ui, Next.js) is built and served separately.
EXPOSE 8000

HEALTHCHECK CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

ENTRYPOINT ["python", "-m", "backend.run"]
