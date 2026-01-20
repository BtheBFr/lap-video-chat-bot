FROM python:3.9-slim

WORKDIR /app

# Копируем все файлы
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r bot/requirements.txt

# Запускаем бота
CMD cd bot && python main.py
