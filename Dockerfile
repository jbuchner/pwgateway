# FROM python:3.12.2-alpine3.19
FROM python:3.12-slim

WORKDIR /code

ENV PYTHONPATH=/code/app

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["uvicorn", "app.pwgateway:app", "--host", "0.0.0.0", "--port", "8081"]

# docker build -t pwgateway .
