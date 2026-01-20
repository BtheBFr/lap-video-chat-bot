FROM python:3.9-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r bot/requirements.txt

# Делаем скрипт исполняемым
RUN chmod +x start.sh

CMD ["./start.sh"]
