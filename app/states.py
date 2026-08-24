from aiogram.fsm.state import State, StatesGroup


class PerfumeForm(StatesGroup):
    location = State()
    event = State()
    outfit = State()
    circumstance = State()
    effect = State()
    target_time = State()
    manual_target_time = State()
    advanced = State()
    time = State()
    season = State()
    exposure = State()
    mode = State()


class RecommendationBrowseForm(StatesGroup):
    active = State()


class ManualLayeringForm(StatesGroup):
    first_brand = State()
    first_perfume = State()
    second_brand = State()
    second_perfume = State()


class PerfumeListForm(StatesGroup):
    brand = State()


class CompareForm(StatesGroup):
    first_brand = State()
    first_perfume = State()
    second_brand = State()
    second_perfume = State()


class ReverseForm(StatesGroup):
    brand = State()
    perfume = State()


class WhyNotForm(StatesGroup):
    brand = State()
    perfume = State()


class FreeTextForm(StatesGroup):
    text = State()


class FeedbackForm(StatesGroup):
    rating = State()
    tags = State()
