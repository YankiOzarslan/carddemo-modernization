FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ${LAMBDA_TASK_ROOT}/
ENV PYTHONPATH=${LAMBDA_TASK_ROOT}

CMD ["carddemo_report.lambda_handler.handler"]
