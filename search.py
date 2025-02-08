from aiogram import Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from io import BytesIO

from sql import Database

db = Database(None)  # Bot instance будет передан в main.py
router = Router()  # Изменено с Dispatcher на Router

class MatchMaking(StatesGroup):
    searching = State()
    viewing = State()

@router.message(Command("findmatch"))
async def find_match(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        return

    preferred_gender = user[7]
    user_gender = user[3]

    db.cursor.execute(
        "SELECT * FROM users WHERE gender = ? AND preferred_gender = ? AND tg_id != ?",
        (preferred_gender, user_gender, message.from_user.id)
    )
    potential_matches = db.cursor.fetchall()

    if not potential_matches:
        await message.answer("К сожалению, подходящих пользователей пока нет.")
        return

    await state.update_data(matches=potential_matches, index=0, likes={})
    await state.set_state(MatchMaking.viewing)
    await show_next_match(message, state)

async def show_next_match(message: Message, state: FSMContext):
    data = await state.get_data()
    matches = data.get("matches", [])
    index = data.get("index", 0)

    if index >= len(matches):
        await message.answer("Вы просмотрели все доступные анкеты.")
        await state.clear()
        return

    match = matches[index]
    profile_info = (
        f"Имя: {match[2]}\n"
        f"Пол: {match[3]}\n"
        f"Возраст: {match[4]}\n"
        f"Город: {match[5]}\n"
    )

    if match[6]:
        photo_data = match[6]
        photo_file = BufferedInputFile(BytesIO(photo_data).getvalue(), filename="profile_photo.jpg")
        await message.answer_photo(photo_file, caption=profile_info)
    else:
        await message.answer(profile_info)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❤ Нравится")],
            [KeyboardButton(text="⏩ Пропустить")]
        ],
        resize_keyboard=True
    )

    await message.answer("Выберите действие:", reply_markup=keyboard)
    await state.update_data(index=index + 1)

@router.message(MatchMaking.viewing)
async def handle_match_action(message: Message, state: FSMContext):
    action = message.text.strip()
    data = await state.get_data()
    matches = data.get("matches", [])
    index = data.get("index", 0)
    likes = data.get("likes", {})

    if index - 1 < len(matches):
        current_match = matches[index - 1]
        match_tg_id = current_match[1]

        if action == "❤ Нравится":
            likes[match_tg_id] = True

            # Проверяем, есть ли взаимный "лайк"
            db.cursor.execute(
                "SELECT * FROM likes WHERE tg_id = ? AND liked_tg_id = ?",
                (match_tg_id, message.from_user.id)
            )
            reciprocal_like = db.cursor.fetchone()

            if reciprocal_like:
                # Уведомляем обоих пользователей
                match_user = db.get_user(match_tg_id)
                current_user = db.get_user(message.from_user.id)

                if match_user and current_user:
                    match_username = f"@{match_user[8]}" if match_user[8] else "(не указан)"
                    current_username = f"@{current_user[8]}" if current_user[8] else "(не указан)"

                    await message.answer(f"У вас совпадение! Пользователь: {match_username}")
                    await message.bot.send_message(match_tg_id, f"У вас совпадение! Пользователь: {current_username}")

                db.cursor.execute(
                    "INSERT INTO likes (tg_id, liked_tg_id) VALUES (?, ?)",
                    (message.from_user.id, match_tg_id)
                )
                db.conn.commit()

            else:
                db.cursor.execute(
                    "INSERT INTO likes (tg_id, liked_tg_id) VALUES (?, ?)",
                    (message.from_user.id, match_tg_id)
                )
                db.conn.commit()

            await message.answer("Вы выразили симпатию!")

        elif action == "⏩ Пропустить":
            await message.answer("Вы пропустили пользователя.")

        else:
            await message.answer("Пожалуйста, выберите действие: ❤ Нравится или ⏩ Пропустить.")
            return

        await show_next_match(message, state)
