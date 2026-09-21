# Personal Perfume Recommendation Bot

Персональный Telegram-бот на **aiogram 3** с детерминированным recommendation engine, FastAPI webhook для Vercel, Open-Meteo forecast, layering, каталогом и опциональной персонализацией.

## Основные функции

- каталог коллекции, сортировка по бренду, фильтр по бренду и полу;
- обычный подбор и `Другие варианты`;
- подбор к конкретному времени: сейчас, +1 ч, +2 ч, вечером, HH:MM;
- Auto time-of-day и Auto season с учетом timezone, даты и полушария;
- structured `Situation` и `OutfitProfile`;
- score 0–100 по событию, климату, эффекту, окружению, одежде, времени, сезону и личной истории;
- hard constraints для экстремальной жары, влажности, small room, close distance и активного спорта;
- confidence score и разнообразный Top-3: лучший / безопасный / более выразительный;
- автоматический layering и curated pairs с постраничным просмотром;
- spray advisor;
- `Почему не этот аромат?` и `Хочу надеть конкретный аромат`;
- опциональный OpenAI-compatible AI parser/reranker;
- feedback и recent wear penalty при настроенном persistent storage;
- `/debug_recommendation` только для владельца.

## Архитектура

```text
app/models/
  situation.py
  outfit.py
  perfume.py
  recommendation.py

app/services/
  situation_parser.py
  outfit_parser.py
  weather.py
  recommender.py
  scoring.py
  scoring_config.py
  layering.py
  spray_advisor.py
  personalization.py
  explanations.py
  ai_client.py
  validator.py
  history.py

app/storage/
  base.py
  memory.py
  redis.py
  factory.py
```

Исходная коллекция остается в `app/data/perfumes.py`. При импорте migration/enrichment layer достраивает расширенный профиль из существующих данных. Если точных top/heart/base notes в старой базе нет, они остаются пустыми — бот не выдумывает пирамиду.

## Локальная установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Минимальный `.env` локально:

```env
BOT_TOKEN=...
OWNER_ID=123456789
APP_ENV=development
```

Локальный polling:

```bash
python run_polling.py
```

## Vercel

Production использует `main.py` и FastAPI webhook. Polling на Vercel не используется.

Vercel Environment Variables:

```env
BOT_TOKEN=...
OWNER_ID=123456789
APP_ENV=production
PUBLIC_URL=https://your-project.vercel.app
WEBHOOK_SECRET=long_random_secret
```

`OWNER_ID` обязателен, если задан `PUBLIC_URL`. Это защищает публично развернутого персонального бота.

После deploy один раз открой:

```text
https://your-project.vercel.app/set-webhook
```

Проверка:

```text
https://your-project.vercel.app/webhook-info
```

`setWebhook` не выполняется на каждом Telegram request.

## Open-Meteo

Ключ не нужен. Для выбранного времени бот запрашивает hourly forecast:

- temperature;
- apparent temperature;
- relative humidity;
- precipitation / rain;
- cloud cover;
- wind speed;
- is_day.

Если hourly forecast не удается сопоставить, используется current weather fallback.

## Persistent storage на Vercel

Локальная файловая система и SQLite не используются для истории.

Предпочтительный вариант — Redis-compatible REST/serverless storage, например Upstash. Поддерживаются:

```env
REDIS_REST_URL=
REDIS_REST_TOKEN=
FSM_TTL_SECONDS=86400
```

Также принимаются aliases:

```text
UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN
KV_REST_API_URL / KV_REST_API_TOKEN
```

При наличии Redis через HTTP сохраняются:

- FSM/session state;
- `preferences`;
- `wear_history`;
- `feedback`;
- `last_situation`;
- `last_location`;
- `last_recommendation`.

Если Redis не настроен:

- бот запускается;
- каталог работает;
- обычный recommender и layering работают;
- используется aiogram `MemoryStorage` для FSM;
- persistent feedback/history отключены.

**Важно:** MemoryStorage на Vercel serverless не гарантирует сохранение FSM между cold starts или разными instances. Для надежного многошагового flow на Vercel настрой Redis REST.

Если Redis настроен, но временно недоступен, FSM storage имеет process-memory fallback, а long-term history gracefully отключается на неудачном запросе.

## Персонализация

После рекомендации доступно `Как прошло?`:

- Отлично;
- Нормально;
- Не понравилось;
- Слишком сильный;
- Слишком слабый.

Дополнительные сигналы:

- Получил комплимент;
- Самому понравилось;
- Устал от аромата;
- Хочу повторить.

Используется простая статистическая модель с time decay. Никакого ML/RAG.

Режим повторов:

```text
/variety    — сильнее штрафовать недавние повторы
/favorites  — слабее штрафовать любимые повторения
```

## Optional AI

AI не нужен для основной работы.

```env
AI_ENABLED=false
AI_API_KEY=
AI_BASE_URL=https://integrate.api.nvidia.com/v1
AI_MODEL=
```

API должен быть OpenAI-compatible (`/chat/completions`).

Если AI включен:

1. свободный текст может быть дополнительно разобран в validated `Situation` JSON;
2. deterministic engine считает всю коллекцию;
3. AI получает только Top-6 + факты + breakdown + warnings;
4. AI может слегка переставить близкие варианты;
5. hard constraints не обходятся;
6. AI не может добавить аромат вне Top-6;
7. при API error используется deterministic result без ошибки для пользователя.

## Быстрый recommendation flow

```text
Подобрать аромат
→ локация
→ событие
→ описание одежды
→ обстановка
→ эффект
→ когда носить
→ Авто — продолжить
→ Обычный парфюм / Наслаивание
```

Ручная настройка `time / season / outdoor exposure` доступна через `Настроить вручную`, но не обязательна.

Если Redis включен, появляются полезные persistent сценарии:

- `Использовать прошлую локацию`;
- `Как в прошлый раз`.

## Debug

Только OWNER_ID:

```text
/debug_recommendation
```

Показывает последнюю нормализованную Situation, final score, subscores, penalties, recent wear penalty, AI adjustment, hard warnings и confidence.

## Тесты

```bash
pytest -q
```

Regression suite содержит 50 ситуационных сценариев и дополнительные тесты:

- extreme humid heat;
- dry/cold/rain/time/event/outfit contexts;
- hard constraints;
- score/confidence ranges;
- diversity;
- auto time;
- hemisphere-aware auto season;
- forecast hour selection;
- OutfitProfile parser;
- curated layering;
- curated pair losing under dangerous heat;
- perfume database validator;
- personalization/recent wear;
- free-text parser;
- spray advisor;
- deterministic reproducibility.

## BotFather

После изменения кода никаких новых действий в BotFather не требуется. Нужен только действующий токен. Если токен когда-либо публиковался, его нужно revoke/regenerate.

## Обновление коллекции 2026-09-18

44 аромата, 946 уникальных пар. Добавлены Stronger With You Powerfully, Born in Roma Uomo Extradose (мужской), Narcotic Delight, Bitter Peach и Gentle Fluidity Silver. Добавлено 10 готовых схем с Molecule 01/02.

Ссылки на источники находятся в `fact_sources` новых записей. `known_notes` хранит подтверждённые ноты без выдуманного разделения на верх, сердце и базу. Числовые оценки, температурные диапазоны и совместимость являются настройками модели, а не измерениями производителя или результатами испытаний на коже. Новые пары требуют личной проверки. Удалённые режимы меню не возвращены.


### Объёмы и необязательный образ, 2026-09-21

В каталоге доступны разделы «5 или 10 мл» (20 ароматов) и «100 мл» (24 аромата).
Это указанные владельцем объёмы флаконов, не остатки жидкости. Точный объём внутри первой группы не определён.
Объём показан в каталоге, рекомендациях и готовых парах, но не влияет на рейтинг.
На шаге одежды кнопка «Пропустить» исключает образ из оценки и объяснений.
Без одежды веса: событие 30%, климат 25%, окружение 15%, время дня 10%, эффект 10%, сезон 5%, личный опыт 5%.
С одеждой сохранены прежние веса. Ограничение отдельного аромата по условиям ограничивает и оценку наслоения с ним.
Оценки остаются эвристическими, а не гарантией восприятия аромата или результатом испытаний сочетаний.
