FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r bot/requirements.txt

# УБИРАЕМ debug_env.py, запускаем только бота
CMD cd bot && python main.py
