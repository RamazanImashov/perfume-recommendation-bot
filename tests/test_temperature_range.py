from unittest.mock import AsyncMock
import pytest
from test_calendar_presets import ui, state


@pytest.mark.asyncio
@pytest.mark.parametrize('text,low,high', [('от 10 до 15',10,15),('от -10 до -5',-10,-5),('10-15',10,15),('-10 - -5',-10,-5),('от -2,5 до +3,5',-2.5,3.5)])
async def test_range_saved_and_displayed(ui,state,text,low,high):
    await state.update_data(target_datetime='2026-12-31T22:15:00+06:00')
    message=AsyncMock(); message.text=text
    await ui.manual_temperature(message,state)
    data=await state.get_data()
    assert data['weather']['temperature_min'] == low
    assert data['weather']['temperature_max'] == high
    assert data['weather']['temperature'] == (low+high)/2
    situation=ui._situation_from_data(data)
    assert situation.temperature_min == low
    assert situation.temperature_max == high
    assert f'от {low:g} до {high:g}°C' in message.answer.call_args.args[0]
    from app.services.recommender import recommend_situation
    from app.services.layering import recommend_layering_situation
    assert f'от {low:g} до {high:g}°C' in ui.format_perfume_results(situation,recommend_situation(situation,1))
    assert f'от {low:g} до {high:g}°C' in ui.format_layering_results(situation,recommend_layering_situation(situation,1))


@pytest.mark.asyncio
@pytest.mark.parametrize('text',['18','от 15 до 10','от -61 до 10','от 10 до 61','nan','от 10 до','10 15'])
async def test_invalid_range_stays_in_input(ui,state,text):
    from app.states import PerfumeForm
    await state.set_state(PerfumeForm.manual_temperature)
    await state.update_data(target_datetime='2026-12-31T22:15:00+06:00')
    message=AsyncMock(); message.text=text
    await ui.manual_temperature(message,state)
    assert await state.get_state() == PerfumeForm.manual_temperature.state
    assert 'weather' not in await state.get_data()
    assert 'диапазон' in message.answer.call_args.args[0]
