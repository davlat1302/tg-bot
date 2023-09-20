from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from aiogram.dispatcher.filters.state import StatesGroup, State
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()
# Создаем подключение к базе данных
engine = create_engine('sqlite:///schedule.db', echo=True)
Session = sessionmaker(bind=engine)
session = Session()

# Создаем базовую модель
Base = declarative_base()



class MyForm(StatesGroup):
    waiting_for_day = State()
    waiting_for_schedule = State()
    waiting_for_day_update = State()
    waiting_for_schedule_update = State()
    waiting_for_day_delete = State()

class Schedule(Base):
    __tablename__ = 'schedule'

    id = Column(Integer, primary_key=True)
    day = Column(String)
    timetable = Column(String)


# Создаем таблицу в базе данных
Base.metadata.create_all(engine)

# Создаем бота и диспетчера
bot = Bot(token=os.getenv("TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply(f"<em>Привет, </em> <b>{message.from_user.first_name}</b>👋<em>! Я бот для просмотра расписания. Введите команду /schedule, чтобы увидеть расписание.</em>",
                        parse_mode='HTML')


# Обработчик команды /schedule
@dp.message_handler(commands=['schedule'])
async def schedule(message: types.Message):
    # Создаем клавиатуру с вариантами дней недели
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="Пн.", callback_data="day_monday"),
        types.InlineKeyboardButton(text="Вт.", callback_data="day_tuesday"),
        types.InlineKeyboardButton(text="Ср.", callback_data="day_wednesday"),
        types.InlineKeyboardButton(text="Чт.", callback_data="day_thursday"),
        types.InlineKeyboardButton(text="Пт.", callback_data="day_friday"),
        types.InlineKeyboardButton(text="Сб.", callback_data="day_saturday"),
    )
    await message.reply("<em>Выберите день недели:</em>",
                        parse_mode='HTML', reply_markup=keyboard)


# Обработчик Inline-кнопок
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('day_'))
async def process_inline_button(callback_query: types.CallbackQuery):
    # Получаем выбранный день недели из callback_data и отправляем расписание на него
    day = callback_query.data.split('_')[1]
    schedule = get_schedule_from_database(day)
    await bot.send_message(callback_query.message.chat.id, f'{day}:' + f'\n{schedule}')
    await callback_query.answer()

# callback_query.from_user.id

# Обработчик команды /admin
@dp.message_handler(commands=['admin'])
async def admin(message: types.Message):
    # Проверяем, является ли отправитель администратором
    if not is_admin(message.from_user.id):
        await message.answer(text='<em>У вас нет доступа к Админке🚫</em>!',
                             parse_mode='HTML')
        return
    
    # Создаем клавиатуру с вариантами административных действий
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton(text="Добавить расписание", callback_data="admin_add_schedule"),
        types.InlineKeyboardButton(text="Обновить расписание", callback_data="admin_update_schedule"),
        types.InlineKeyboardButton(text="Удалить расписание", callback_data="admin_delete_schedule"),
    )
    await message.reply("Выберите действие:", reply_markup=keyboard)


kb = [
        [
            types.KeyboardButton(text="monday"),
            types.KeyboardButton(text="tuesday"),
            types.KeyboardButton(text="wednesday"),
            types.KeyboardButton(text="thursday"),
            types.KeyboardButton(text="friday"),
            types.KeyboardButton(text="saturday")
        ],
    ]
keyboard = types.ReplyKeyboardMarkup(
    keyboard=kb,
    resize_keyboard=True,
    )

keyboard_rem = types.ReplyKeyboardRemove(True)


# Обработчик Inline-кнопок административных действий
@dp.callback_query_handler(lambda callback_data: callback_data.data and callback_data.data.startswith('admin_'))
async def process_admin_button(callback_query: types.CallbackQuery):
    # Проверяем, является ли отправитель администратором
    if not is_admin(callback_query.from_user.id):
        return
    
    action = callback_query.data.split('_')[1]
    await callback_query.answer()

    
    
    if action == "add":
        await bot.send_message(callback_query.from_user.id, "<em>📆Введите день недели:</em>", parse_mode='HTML', reply_markup=keyboard)
        # Ожидаем следующее сообщение пользователя в качестве дня недели
        await MyForm.waiting_for_day.set()
    elif action == "update":
        await bot.send_message(callback_query.from_user.id, "<em>📆Введите день недели для обновления:</em>", parse_mode='HTML', reply_markup=keyboard)
        # Ожидаем следующее сообщение пользователя в качестве дня недели
        await MyForm.waiting_for_day_update.set()
    elif action == "delete":
        await bot.send_message(callback_query.from_user.id, "<em>📆Введите день недели для удаления:</em>", parse_mode='HTML', reply_markup=keyboard)
        # Ожидаем следующее сообщение пользователя в качестве дня недели
        await MyForm.waiting_for_day_delete.set()


# Обработчик сообщений в режиме ожидания дня недели для добавления расписания
@dp.message_handler(state=MyForm.waiting_for_day)
async def process_day_for_add_schedule(message: types.Message, state: FSMContext):
    day = message.text
    # Сохраняем день недели в состояние FSM
    await state.update_data(day=day)
    await bot.send_message(message.from_user.id, "Введите расписание:", reply_markup=keyboard_rem)
    # Ожидаем следующее сообщение пользователя в качестве расписания
    await MyForm.waiting_for_schedule.set()


# Обработчик сообщений в режиме ожидания расписания для добавления расписания
@dp.message_handler(state=MyForm.waiting_for_schedule)
async def process_schedule_for_add_schedule(message: types.Message, state: FSMContext):
    # Получаем данные из состояния FSM
    data = await state.get_data()
    day = data['day']
    timetable = message.text
    
    # Создаем новую запись в базе данных
    new_schedule = Schedule(day=day, timetable=timetable)
    session.add(new_schedule)
    session.commit()
    
    await state.finish()
    await bot.send_message(message.from_user.id, "<em>Расписание успешно добавлено👌</em>!",
                           parse_mode='HTML')


# Обработчик сообщений в режиме ожидания дня недели для обновления расписания
@dp.message_handler(state=MyForm.waiting_for_day_update)
async def process_day_for_update_schedule(message: types.Message, state: FSMContext):
    day = message.text
    # Сохраняем день недели в состояние FSM
    await state.update_data(day=day)
    await bot.send_message(message.from_user.id, "<em>Введите новое расписание:</em>",
                           parse_mode='HTML', reply_markup=keyboard_rem)
    # Ожидаем следующее сообщение пользователя в качестве нового расписания
    await MyForm.waiting_for_schedule_update.set()


# Обработчик сообщений в режиме ожидания нового расписания для обновления расписания
@dp.message_handler(state=MyForm.waiting_for_schedule_update)
async def process_schedule_for_update_schedule(message: types.Message, state: FSMContext):
    # Получаем данные из состояния FSM
    data = await state.get_data()
    day = data['day']
    timetable = message.text
    
    # Обновляем запись в базе данных
    schedule = session.query(Schedule).filter_by(day=day).first()
    if schedule:
        schedule.timetable = timetable
        session.commit()
        await state.finish()
        await bot.send_message(message.from_user.id, "<em>Расписание успешно обновлено👌!</em>",
                               parse_mode='HTML')
    else:
        await state.finish()
        await bot.send_message(message.from_user.id, "<em>Расписание для данного дня не найдено🤷‍♂️.</em>",
                               parse_mode='HTML')


# Обработчик сообщений в режиме ожидания дня недели для удаления расписания
@dp.message_handler(state=MyForm.waiting_for_day_delete)
async def process_day_for_delete_schedule(message: types.Message, state: FSMContext):
    day = message.text
    # Удаляем запись из базы данных
    schedule = session.query(Schedule).filter_by(day=day).first()
    if schedule:
        session.delete(schedule)
        session.commit()
        await state.finish()
        await bot.send_message(message.from_user.id, "<em>Расписание успешно удалено👌!</em>",
                               parse_mode='HTML')
    else:
        await state.finish()
        await bot.send_message(message.from_user.id, "<em>Расписание для данного дня не найдено🤷‍♂️.</em>",
                               parse_mode='HTML')


# Функция для проверки является ли пользователь администратором
def is_admin(user_id):
    # Здесь вы можете добавить свою логику проверки администратора, например, с помощью списка администраторов
    admins = [699536364, 5232384737, 5727807505]  # Пример списка администраторов
    return user_id in admins


def get_schedule_from_database(day):
    schedule = session.query(Schedule).filter_by(day=day).first()
    if schedule:
        return schedule.timetable
    else:
        return "Расписание для данного дня не найдено🤷‍♂️."


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)