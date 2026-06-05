from aiogram.fsm.state import State, StatesGroup


class PerfumeForm(StatesGroup):
    location = State()
    event = State()
    outfit = State()
    circumstance = State()
    effect = State()
    time_of_day = State()
    season = State()


class LayeringForm(StatesGroup):
    first = State()
    second = State()

