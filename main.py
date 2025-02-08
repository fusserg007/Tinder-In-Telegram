from aiogram import Bot, Dispatcher
from aiogram.types import Message, InputFile, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types.input_file import FSInputFile
from aiogram.fsm.state import StatesGroup, State
from io import BytesIO
import logging
from aiogram.types import ReplyKeyboardRemove 

from config import BOT_TOKEN
from sql import Database
from search import router as search_router


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database(bot)

class Registration(StatesGroup):
    name = State()
    gender = State()
    age = State()
    city = State()
    photo = State()
    preferred_gender = State()

class EditProfile(StatesGroup):
    field = State()
    value = State()

@dp.message(Command('start'))
async def start(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if user:
        await message.answer("Вы уже зарегистрированы! Используйте /myprofile для просмотра или /editprofile для редактирования анкеты.")
    else:
        await state.update_data(username=message.from_user.username)  # Добавляем username в данные
        await message.answer("Добро пожаловать! Перед началом проверьте, что у вас есть username в Телеграмм, в противном случае вам никто не сможет написать при взаимной симпатии. Как вас зовут?")
        await state.set_state(Registration.name)

@dp.message(Registration.name)
async def collect_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    
    # Создаем клавиатуру для выбора пола
    gender_markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="М"), KeyboardButton(text="Ж")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Ваш пол?", reply_markup=gender_markup)
    await state.set_state(Registration.gender)

@dp.message(Registration.gender)
async def collect_gender(message: Message, state: FSMContext):
    gender = message.text.strip().lower()
    if gender not in ['м', 'ж']:
        # Повторяем запрос с клавиатурой, если ввод некорректен
        gender_markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="М"), KeyboardButton(text="Ж")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("Пожалуйста, выберите пол используя кнопки ниже:", reply_markup=gender_markup)
        return
    
    await state.update_data(gender=gender.upper())
    
    # Переходим к следующему вопросу, оставляем клавиатуру
    await message.answer("Сколько вам лет?")
    await state.set_state(Registration.age)

@dp.message(Registration.age)
async def collect_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        if age < 18:
            await message.answer("Извините, вы должны быть старше 18 лет для использования бота.")
            return
        await state.update_data(age=age)
        await message.answer("Из какого вы города?")
        await state.set_state(Registration.city)
    except ValueError:
        await message.answer("Введите корректный возраст.")

@dp.message(Registration.city)
async def collect_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    
    # Создаем клавиатуру для выбора предпочтений, без удаления клавиатуры
    preferred_gender_markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="М"), KeyboardButton(text="Ж")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Кого вы ищете для общения?", reply_markup=preferred_gender_markup)
    await state.set_state(Registration.preferred_gender)

@dp.message(Registration.preferred_gender)
async def collect_preferred_gender(message: Message, state: FSMContext):
    preferred_gender = message.text.strip().lower()
    if preferred_gender not in ['м', 'ж']:
        preferred_gender_markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="М"), KeyboardButton(text="Ж")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("Пожалуйста, выберите предпочтение используя кнопки ниже:", reply_markup=preferred_gender_markup)
        return
    
    await state.update_data(preferred_gender=preferred_gender.upper())
    
    # Оставляем клавиатуру и переходим к следующему шагу
    await message.answer("Отправьте ваше фото или пропустите шаг с помощью команды /skip.")



@dp.message(Registration.photo)
async def collect_photo(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Пожалуйста, отправьте фотографию или пропустите этот шаг с помощью команды /skip.")
        return

    file_id = message.photo[-1].file_id
    user_data = await state.get_data()
    user_data['photo'] = file_id
    await db.save_user(message.from_user.id, user_data)
    await message.answer("Регистрация завершена!")
    await state.clear()

@dp.message(Command("skip"))
async def skip_photo(message: Message, state: FSMContext):
    user_data = await state.get_data()
    await db.save_user(message.from_user.id, user_data)
    await message.answer("Регистрация завершена!")
    await state.clear()

@dp.message(Command("myprofile"))
async def myprofile(message: Message):
    user = db.get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start для регистрации.")
        return

    profile_info = (
        f"Имя: {user[2]}\n"
        f"Пол: {user[3]}\n"
        f"Возраст: {user[4]}\n"
        f"Город: {user[5]}\n"
        f"Ищет: {user[7]}\n"
    )

    if user[6]:
        photo_data = user[6]
        photo_file = BufferedInputFile(BytesIO(photo_data).getvalue(), filename="profile_photo.jpg")
        await message.answer_photo(photo_file, caption=profile_info)
    else:
        await message.answer(profile_info)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db.init_db()

    # Подключение обработчиков из search.py
    dp.include_router(search_router)

    dp.run_polling(bot)
