from aiogram.fsm.state import State, StatesGroup


class PerfumeForm(StatesGroup):
    location = State()
    event = State()
    outfit = State()
    circumstance = State()
    effect = State()
    time = State()
    season = State()
    mode = State()


class ManualLayeringForm(StatesGroup):
    first_perfume = State()
    second_perfume = State()


class PerfumeListForm(StatesGroup):
    brand = State()
