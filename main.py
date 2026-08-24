from __future__ import annotations

import logging

from aiogram.types import Update
from fastapi import FastAPI, HTTPException, Request

from app.bot import bot, config, dp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()
WEBHOOK_PATH = f"/webhook/{config.webhook_secret}"


@app.get("/")
async def home():
    return {"status": "Perfume bot FastAPI is running", "storage": "redis" if config.redis_rest_url else "memory-fallback"}


@app.get("/set-webhook")
async def set_webhook():
    if not config.public_url:
        raise HTTPException(status_code=500, detail="PUBLIC_URL is not set")
    webhook_url = f"{config.public_url.rstrip('/')}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    info = await bot.get_webhook_info()
    return {"status": "webhook set", "webhook_url": webhook_url, "telegram_webhook_info": info.model_dump()}


@app.get("/webhook-info")
async def webhook_info():
    return (await bot.get_webhook_info()).model_dump()


@app.get("/delete-webhook")
async def delete_webhook():
    await bot.delete_webhook(drop_pending_updates=True)
    return {"status": "webhook deleted"}


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
        return {"ok": True}
    except Exception:
        logger.exception("Webhook update failed")
        return {"ok": False}
