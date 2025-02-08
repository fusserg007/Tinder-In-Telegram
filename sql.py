import sqlite3
from config import DB_PATH
from aiogram import Bot
from io import BytesIO
from PIL import Image
import io

class Database:
    def __init__(self, bot: Bot):
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self.bot = bot

    def init_db(self):
        # Создание таблицы пользователей
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               tg_id INTEGER UNIQUE,
                               name TEXT,
                               gender TEXT,
                               age INTEGER,
                               city TEXT,
                               photo BLOB,
                               preferred_gender TEXT,
                               username TEXT
                               )''')

        # Создание таблицы лайков
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS likes (
                               id INTEGER PRIMARY KEY AUTOINCREMENT,
                               tg_id INTEGER,
                               liked_tg_id INTEGER,
                               FOREIGN KEY (tg_id) REFERENCES users (tg_id),
                               FOREIGN KEY (liked_tg_id) REFERENCES users (tg_id)
                               )''')

        self.conn.commit()

    async def save_user(self, tg_id, data):
        photo = None
        username = data.get('username', None)

        if data.get('photo'):
            file_id = data['photo']
            file = await self.bot.get_file(file_id)
            file_path = file.file_path
            downloaded_file = await self.bot.download_file(file_path)
            photo = downloaded_file.getvalue()

        self.cursor.execute('''INSERT INTO users (tg_id, name, gender, age, city, photo, preferred_gender, username)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(tg_id) DO UPDATE SET
                               name=excluded.name,
                               gender=excluded.gender,
                               age=excluded.age,
                               city=excluded.city,
                               photo=excluded.photo,
                               preferred_gender=excluded.preferred_gender,
                               username=excluded.username''',
                            (tg_id, data['name'], data['gender'], data['age'], data['city'], photo, data.get('preferred_gender'), username))
        self.conn.commit()

    def get_user(self, tg_id):
        self.cursor.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,))
        user = self.cursor.fetchone()
        if user is None:
            return None
        # Если кортеж меньше ожидаемого размера, дополним его пустыми значениями
        return user + (None,) * (9 - len(user))  # Предполагаем, что 9 столбцов

    def update_user_field(self, tg_id, field, value):
        valid_fields = ['name', 'gender', 'age', 'city', 'photo', 'preferred_gender', 'username']
        if field not in valid_fields:
            raise ValueError("Некорректное поле для обновления.")

        self.cursor.execute(f"UPDATE users SET {field} = ? WHERE tg_id = ?", (value, tg_id))
        self.conn.commit()

    def save_like(self, tg_id, liked_tg_id):
        self.cursor.execute('''INSERT INTO likes (tg_id, liked_tg_id) VALUES (?, ?)''', (tg_id, liked_tg_id))
        self.conn.commit()

    def check_reciprocal_like(self, tg_id, liked_tg_id):
        self.cursor.execute('''SELECT * FROM likes WHERE tg_id = ? AND liked_tg_id = ?''', (liked_tg_id, tg_id))
        return self.cursor.fetchone()

    def close(self):
        self.conn.close()
