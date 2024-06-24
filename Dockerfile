FROM python:3.9-buster

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . /bot
WORKDIR /bot

COPY requirements.txt requirements.txt
RUN apt update && apt install nano && pip install --no-cache-dir -r requirements.txt

CMD python3 bot.py
