from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

remove_keyboard = ReplyKeyboardRemove()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Подобрать аромат")],
            [KeyboardButton(text="Наслаивание вручную")],
            [KeyboardButton(text="Все мои парфюмы")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить геолокацию", request_location=True)],
            [KeyboardButton(text="Ввести город вручную")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def event_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Учеба"), KeyboardButton(text="Обычный день")],
            [KeyboardButton(text="Прогулка"), KeyboardButton(text="Кафе")],
            [KeyboardButton(text="Свидание"), KeyboardButton(text="Ресторан")],
            [KeyboardButton(text="Клуб"), KeyboardButton(text="День рождения")],
            [KeyboardButton(text="Важная встреча"), KeyboardButton(text="Спорт / активный день")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def circumstance_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Улица"), KeyboardButton(text="Помещение")],
            [KeyboardButton(text="Маленькое помещение"), KeyboardButton(text="Клуб / шумное место")],
            [KeyboardButton(text="Близкая дистанция")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def effect_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Чисто"), KeyboardButton(text="Дорого")],
            [KeyboardButton(text="Сексуально"), KeyboardButton(text="Заметно")],
            [KeyboardButton(text="Спокойно"), KeyboardButton(text="Необычно")],
            [KeyboardButton(text="Не важно")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def time_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Авто")],
            [KeyboardButton(text="Утро"), KeyboardButton(text="День")],
            [KeyboardButton(text="Вечер"), KeyboardButton(text="Ночь")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def season_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Авто")],
            [KeyboardButton(text="Весна"), KeyboardButton(text="Лето")],
            [KeyboardButton(text="Осень"), KeyboardButton(text="Зима")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )


def recommendation_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Обычный парфюм")],
            [KeyboardButton(text="Наслаивание")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True,
    )
