FROM python:latest

WORKDIR /app/
COPY ./utils /app/utils
COPY ./wmp_backend /app/wmp_backend/
ENV PYTHONPATH="$PYTHONPATH:/app/utils:/app/mangement"
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
WORKDIR /app/wmp_backend
CMD python wmp_backend_api.py
