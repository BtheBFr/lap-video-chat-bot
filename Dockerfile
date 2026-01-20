FROM python:3.9

WORKDIR /app

COPY . .

COPY bot/.env .env 2>/dev/null || :

RUN pip install -r bot/requirements.txt

CMD python bot/main.py
