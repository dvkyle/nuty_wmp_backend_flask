FROM python:latest

WORKDIR /app
COPY ./utils /app/utils
COPY ./media-server /app/media-server
ENV PYTHONPATH="$PYTHONPATH:/app/utils"
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
CMD python /app/media-server/media_server.py
