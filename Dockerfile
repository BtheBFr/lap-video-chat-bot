FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r bot/requirements.txt

# Запускаем отладку перед ботом
CMD cd bot && python debug_env.py && echo "---" && python main.py
