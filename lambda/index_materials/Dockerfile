FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .
RUN pip install --only-binary=tiktoken -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY . ${LAMBDA_TASK_ROOT}

CMD ["handler.lambda_handler"]
