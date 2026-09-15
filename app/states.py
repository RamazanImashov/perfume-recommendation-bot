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


class PerfumeListForm(StatesGroup):
    brand = State()


class ReverseForm(StatesGroup):
    brand = State()
    perfume = State()


class WhyNotForm(StatesGroup):
    brand = State()
    perfume = State()


class PresetLayeringBrowseForm(StatesGroup):
    active = State()


class FeedbackForm(StatesGroup):
    rating = State()
    tags = State()
