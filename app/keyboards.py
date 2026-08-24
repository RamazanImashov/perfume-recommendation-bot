from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

remove_keyboard = ReplyKeyboardRemove()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Подобрать аромат"), KeyboardButton(text="Быстрый запрос")],
        [KeyboardButton(text="Хочу надеть конкретный аромат")],
        [KeyboardButton(text="Сравнить ароматы"), KeyboardButton(text="Почему не этот аромат?")],
        [KeyboardButton(text="Наслаивание вручную"), KeyboardButton(text="Готовые пары наслаивания")],
        [KeyboardButton(text="Все мои парфюмы")],
        [KeyboardButton(text="Как в прошлый раз")],
        [KeyboardButton(text="Отмена")],
    ], resize_keyboard=True)


def recommendation_result_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Другие варианты")],
        [KeyboardButton(text="Как прошло?")],
        [KeyboardButton(text="Почему не этот аромат?"), KeyboardButton(text="Сравнить ароматы")],
        [KeyboardButton(text="Подобрать аромат"), KeyboardButton(text="Главное меню")],
    ], resize_keyboard=True)


def location_keyboard(has_previous: bool = False) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="Отправить геолокацию", request_location=True)], [KeyboardButton(text="Ввести город вручную")]]
    if has_previous:
        rows.append([KeyboardButton(text="Использовать прошлую локацию")])
    rows.append([KeyboardButton(text="Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def event_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Учеба"), KeyboardButton(text="Работа")],
        [KeyboardButton(text="Важная встреча"), KeyboardButton(text="Обычный день")],
        [KeyboardButton(text="Прогулка"), KeyboardButton(text="Кафе")],
        [KeyboardButton(text="Свидание"), KeyboardButton(text="Ресторан")],
        [KeyboardButton(text="Клуб"), KeyboardButton(text="День рождения")],
        [KeyboardButton(text="Спорт / активный день")], [KeyboardButton(text="Отмена")],
    ], resize_keyboard=True)


def circumstance_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Улица"), KeyboardButton(text="Помещение")],
        [KeyboardButton(text="Маленькое помещение"), KeyboardButton(text="Клуб / шумное место")],
        [KeyboardButton(text="Близкая дистанция")], [KeyboardButton(text="Отмена")],
    ], resize_keyboard=True)


def effect_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Чисто"), KeyboardButton(text="Дорого")],
        [KeyboardButton(text="Сексуально"), KeyboardButton(text="Заметно")],
        [KeyboardButton(text="Спокойно"), KeyboardButton(text="Необычно")],
        [KeyboardButton(text="Не важно")], [KeyboardButton(text="Отмена")],
    ], resize_keyboard=True)


def target_time_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Сейчас"), KeyboardButton(text="Через 1 час")],
        [KeyboardButton(text="Через 2 часа"), KeyboardButton(text="Вечером")],
        [KeyboardButton(text="Указать время")], [KeyboardButton(text="Отмена")],
    ], resize_keyboard=True)


def advanced_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Авто — продолжить")], [KeyboardButton(text="Настроить вручную")], [KeyboardButton(text="Отмена")]], resize_keyboard=True)


def time_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Авто")], [KeyboardButton(text="Утро"), KeyboardButton(text="День")], [KeyboardButton(text="Вечер"), KeyboardButton(text="Ночь")], [KeyboardButton(text="Отмена")]], resize_keyboard=True)


def season_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Авто")], [KeyboardButton(text="Весна"), KeyboardButton(text="Лето")], [KeyboardButton(text="Осень"), KeyboardButton(text="Зима")], [KeyboardButton(text="Отмена")]], resize_keyboard=True)


def exposure_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Авто")], [KeyboardButton(text="Мало улицы"), KeyboardButton(text="Средне")], [KeyboardButton(text="Много улицы")], [KeyboardButton(text="Отмена")]], resize_keyboard=True)


def recommendation_mode_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Обычный парфюм")], [KeyboardButton(text="Наслаивание")], [KeyboardButton(text="Отмена")]], resize_keyboard=True)


def perfume_list_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Все по брендам")], [KeyboardButton(text="Фильтр по бренду")], [KeyboardButton(text="Мужские"), KeyboardButton(text="Женские")], [KeyboardButton(text="Унисекс")], [KeyboardButton(text="Отмена")]], resize_keyboard=True)


def brand_keyboard(brands: list[str]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=brand) for brand in brands[i:i + 2]] for i in range(0, len(brands), 2)]
    rows.append([KeyboardButton(text="Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def perfume_keyboard(perfumes: list[dict]) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=f"{p.get('name')} — {p.get('brand')}")] for p in perfumes]
    rows.append([KeyboardButton(text="Отмена")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def feedback_rating_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Отлично"), KeyboardButton(text="Нормально")],
        [KeyboardButton(text="Не понравилось")],
        [KeyboardButton(text="Слишком сильный"), KeyboardButton(text="Слишком слабый")],
        [KeyboardButton(text="Отмена")],
    ], resize_keyboard=True)


def feedback_tags_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Получил комплимент"), KeyboardButton(text="Самому понравилось")],
        [KeyboardButton(text="Устал от аромата"), KeyboardButton(text="Хочу повторить")],
        [KeyboardButton(text="Готово")],
    ], resize_keyboard=True)
