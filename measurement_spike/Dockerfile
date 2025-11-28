FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

# system deps for mediapipe/opencv may be heavy; keep base minimal for the spike
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
RUN mkdir -p /app/uploads

EXPOSE 5000
CMD ["python", "app.py"]
