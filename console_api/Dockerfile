FROM python:latest

WORKDIR /app
COPY ./utils /app/utils
COPY ./management/load*.py /app/management/
COPY ./console_api /app/console_api/
ENV PYTHONPATH="$PYTHONPATH:/app/utils:/app/mangement"
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
CMD python /app/console_api/site_api.py
