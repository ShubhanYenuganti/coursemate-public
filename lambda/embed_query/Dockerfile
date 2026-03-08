FROM python:3.12-slim

# Install Python dependencies + Lambda Runtime Interface Client
COPY requirements.txt .
RUN pip install --no-cache-dir awslambdaric -r requirements.txt && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
WORKDIR /var/task
COPY handler.py .

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
