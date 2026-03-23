FROM python:3.12-slim

# Install tesseract OCR (Debian repos have it out of the box)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Python dependencies + Lambda Runtime Interface Client
COPY requirements.txt .
RUN pip install --no-cache-dir awslambdaric -r requirements.txt

ENV JINA_API_KEY=""

# Copy application code
WORKDIR /var/task
COPY handler.py embedder.py db.py ./
COPY extractors/ ./extractors/
COPY chunkers/ ./chunkers/

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
