FROM python:3.9

WORKDIR /app

COPY . .

RUN pip install -r bot/requirements.txt

CMD python bot/main.py
