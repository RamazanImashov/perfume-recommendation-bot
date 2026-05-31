from aiogram.fsm.state import State, StatesGroup


class PerfumeForm(StatesGroup):
    location = State()
    event = State()
    outfit = State()
    circumstance = State()
    effect = State()
