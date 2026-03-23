FROM python:3.12-slim

# Install Python dependencies + Lambda Runtime Interface Client
COPY requirements.txt .
RUN pip install --no-cache-dir awslambdaric -r requirements.txt

# Copy application code
WORKDIR /var/task
COPY handler.py worker.py embedder.py chunker.py db.py ./
COPY extractors/ ./extractors/
COPY chunkers/ ./chunkers/

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
