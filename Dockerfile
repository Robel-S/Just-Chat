FROM python:3.14.4-slim

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /chat-app

COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . .