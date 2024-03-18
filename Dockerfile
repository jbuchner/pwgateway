FROM python:3.12-slim

WORKDIR /code

EXPOSE 8080

ENV PYTHONPATH=/code/app

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY ./app /code/app

CMD ["uvicorn", "app.pwgateway:app", "--host", "0.0.0.0", "--port", "8081"]

# docker build -t jbuchner/pwplugin .
# docker buildx build --platform linux/arm/v7,linux/arm64/v8,linux/amd64 -t jbuchner/pwplugin --push .
# docker push jbuchner/pwplugin
