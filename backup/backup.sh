#!/bin/bash

# Папки с базами данных
BOT_DB="/app/bot/users.db"  # Укажите путь к базе данных Telegram бота // тут почты пользователей
MAIN_DB="/app/main/users.db"  # Укажите путь к базе данных FastAPI Тут конфиги

# Папка для резервных копий
BACKUP_DIR="/app/backups"

# Создаем папку для резервных копий, если она не существует
mkdir -p $BACKUP_DIR

while true; do
    # Копируем базы данных
    cp $BOT_DB $BACKUP_DIR/bot_db_$(date +%Y%m%d%H%M%S).db
    cp $MAIN_DB $BACKUP_DIR/main_db_$(date +%Y%m%d%H%M%S).db

    # Ждем 3 часа
    sleep 10800
done