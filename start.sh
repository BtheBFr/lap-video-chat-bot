#!/bin/bash

# Запускаем статический сервер в фоне
python3 -m http.server 8000 --directory static &

# Ждем немного
sleep 2

# Запускаем бота
cd bot
python3 main.py
