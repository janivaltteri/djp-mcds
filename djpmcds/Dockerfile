FROM python:3.8.1-slim-buster

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y gcc libpq-dev libffi-dev netcat curl tree

RUN mkdir -p /opt/djpmcds/celery
RUN mkdir -p /opt/djpmcds/postgres
RUN mkdir -p /opt/djpmcds/files/datafiles
RUN mkdir -p /opt/djpmcds/files/dataspecs
RUN mkdir -p /opt/djpmcds/files/downloads
RUN mkdir -p /opt/djpmcds/files/fieldforms

COPY requirements.txt /opt/djpmcds/requirements.txt
WORKDIR /opt/djpmcds
RUN pip3 install -r requirements.txt
COPY . /opt/djpmcds

ENTRYPOINT ["/opt/djpmcds/entrypoint-djpmcds.sh"]
