FROM python:3.12-slim

COPY requirements.txt .
RUN pip install --no-cache-dir awslambdaric -r requirements.txt

WORKDIR /var/task
COPY handler.py db.py ./

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["handler.lambda_handler"]
