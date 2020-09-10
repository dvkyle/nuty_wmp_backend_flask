FROM python:latest

WORKDIR /app
COPY ./utils /app/utils
COPY ./reporting /app/reporting
ENV PYTHONPATH="$PYTHONPATH:/app/utils"
COPY ./requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
CMD python /app/reporting/reports.py
