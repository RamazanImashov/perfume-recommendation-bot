from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock
import importlib
import pytest
from app.services.layering import get_preset_layering_pairs


def test_presets_have_report_metadata_and_unique_pairs():
    pairs = get_preset_layering_pairs()
    keys = [frozenset((p['base']['name'], p['top']['name'])) for p in pairs]
    assert len(keys) == len(set(keys))
    assert any(p.get('report_source') for p in pairs)
    assert sum(p.get('first_test', False) for p in pairs) == 12
    assert all(p.get('seasons') and p.get('times') for p in pairs)
    assert any({p['base']['name'], p['top']['name']} == {'Narcotic Delight', 'Oud Wood'} for p in pairs)


@pytest.mark.parametrize('season', ['spring', 'summer', 'autumn', 'winter'])
def test_season_and_time_filter(season):
    pairs = get_preset_layering_pairs(season=season, time_of_day='day')
    assert pairs
    assert all(season in p['seasons'] and 'day' in p['times'] for p in pairs)


@pytest.fixture
def ui(monkeypatch):
    from app import config
    monkeypatch.setattr(config, 'load_config', lambda: config.Config(bot_token='123456:test'))
    bot = importlib.import_module('app.bot')
    monkeypatch.setattr(bot, 'config', config.Config(bot_token='123456:test'))
    monkeypatch.setattr(bot, '_local_now', lambda tz: datetime(2026, 9, 30, 12, tzinfo=ZoneInfo('Asia/Bishkek')))
    return bot


@pytest.mark.asyncio
async def test_weather_failure_requests_manual_temperature(ui, monkeypatch):
    monkeypatch.setattr(ui, 'get_weather', AsyncMock(side_effect=RuntimeError('offline')))
    state = AsyncMock(); state.get_data.return_value = {'latitude':42, 'longitude':74, 'timezone':'Asia/Bishkek'}
    message = AsyncMock()
    await ui._after_target_time(message, state, datetime(2026,10,3,20,30,tzinfo=ZoneInfo('Asia/Bishkek')))
    from app.states import PerfumeForm
    assert state.set_state.call_args.args[0] == PerfumeForm.manual_temperature
    assert 'температуру' in message.answer.call_args.args[0]


@pytest.mark.asyncio
async def test_today_requests_time(ui):
    state=AsyncMock(); state.get_data.return_value={'timezone':'Asia/Bishkek'}
    message=AsyncMock(); message.text='Сегодня'
    await ui.get_target_time(message,state)
    from app.states import PerfumeForm
    assert state.set_state.call_args.args[0] == PerfumeForm.manual_target_time
    assert state.update_data.call_args.kwargs['selected_date'] == '2026-09-30'


@pytest.fixture
def state():
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.storage.base import StorageKey
    return FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['29.09.2026', '31.02.2027', '2026-10-03', '03.13.2026'])
async def test_invalid_dates_do_not_advance(ui, state, text):
    from app.states import PerfumeForm
    await state.set_state(PerfumeForm.manual_date)
    await state.update_data(timezone='Asia/Bishkek')
    message=AsyncMock(); message.text=text
    await ui.manual_date(message,state)
    assert await state.get_state() == PerfumeForm.manual_date.state
    assert 'selected_date' not in await state.get_data()


@pytest.mark.asyncio
async def test_exact_future_date_time_and_timezone(ui, state, monkeypatch):
    await state.update_data(timezone='Asia/Bishkek')
    message=AsyncMock(); message.text='03.10.2026'
    await ui.manual_date(message,state)
    message.text='20:30'
    after=AsyncMock(); monkeypatch.setattr(ui, '_after_target_time', after)
    await ui.manual_target_time(message,state)
    target=after.call_args.args[2]
    assert target.isoformat() == '2026-10-03T20:30:00+06:00'


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['24:00', '20:99', '8:30', 'nan', '11:59'])
async def test_invalid_or_past_time_not_rolled_to_tomorrow(ui,state,monkeypatch,text):
    await state.update_data(timezone='Asia/Bishkek',selected_date='2026-09-30')
    after=AsyncMock(); monkeypatch.setattr(ui, '_after_target_time',after)
    message=AsyncMock(); message.text=text
    await ui.manual_target_time(message,state)
    after.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_temperature_preserves_selected_datetime(ui,state):
    from app.states import PerfumeForm
    await state.update_data(target_datetime='2026-12-31T22:15:00+06:00')
    message=AsyncMock(); message.text='-5,5'
    await ui.manual_temperature(message,state)
    data=await state.get_data()
    assert data['weather']['temperature'] == -5.5
    assert data['weather']['source'] == 'manual'
    assert data['target_datetime'] == '2026-12-31T22:15:00+06:00'
    assert await state.get_state() == PerfumeForm.advanced.state


@pytest.mark.asyncio
async def test_preset_filter_and_paging_keep_selected_context(ui,state):
    from app.services.situation_parser import build_situation
    current=build_situation(event='restaurant',outfit_text='',circumstance='indoor',effect='any',weather={'temperature':8},target_datetime=datetime(2026,11,3,20,30,tzinfo=ZoneInfo('Asia/Bishkek')),latitude=42,timezone='Asia/Bishkek')
    await state.update_data(recommendation_context={'situation':current.model_dump(mode='json')})
    message=AsyncMock()
    await ui.preset_layering(message,state)
    message.text='По выбранной дате и времени'
    await ui.preset_select_season(message,state)
    assert '03.11.2026 20:30' in message.answer.call_args.args[0]
    data=await state.get_data()
    assert data['preset_season']=='autumn' and data['preset_time']=='evening'
    expected=get_preset_layering_pairs(current,season='autumn',time_of_day='evening')
    page=message.answer.call_args.args[0]
    assert expected[0]['base']['name'] in page
    await ui.more_preset_layering(message,state)
    assert (await state.get_data())['preset_offset']==12
    assert 'осень, вечер' in message.answer.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('target', ['2026-10-20T20:00:00+06:00','2026-09-29T20:00:00+06:00'])
async def test_weather_rejects_forecast_outside_response(monkeypatch,target):
    from app.services import weather
    response=AsyncMock()
    response.raise_for_status=lambda:None
    response.json.return_value={'timezone':'Asia/Bishkek','hourly':{'time':['2026-09-30T00:00','2026-10-02T23:00'],'temperature_2m':[10,20]},'current':{'temperature_2m':25}}
    session=AsyncMock()
    session.get=lambda *a,**kw: response
    response.__aenter__.return_value=response
    session.__aenter__.return_value=session
    monkeypatch.setattr(weather.aiohttp,'ClientSession',lambda **kw:session)
    with pytest.raises(weather.ForecastUnavailable):
        await weather.get_weather(42,74,datetime.fromisoformat(target),'Asia/Bishkek')


@pytest.mark.asyncio
async def test_weather_returns_selected_forecast_not_current(monkeypatch):
    from app.services import weather
    response=AsyncMock(); response.raise_for_status=lambda:None
    response.json.return_value={'timezone':'Asia/Bishkek','hourly':{'time':['2026-09-30T19:00','2026-09-30T20:00'],'temperature_2m':[10,12]},'current':{'temperature_2m':25}}
    session=AsyncMock(); session.get=lambda *a,**kw:response
    response.__aenter__.return_value=response;session.__aenter__.return_value=session
    monkeypatch.setattr(weather.aiohttp,'ClientSession',lambda **kw:session)
    result=await weather.get_weather(42,74,datetime.fromisoformat('2026-09-30T20:00:00+06:00'),'Asia/Bishkek')
    assert result['temperature']==12 and result['forecast_time']=='2026-09-30T20:00'
