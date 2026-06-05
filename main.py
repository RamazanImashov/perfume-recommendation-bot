import os
import logging

from fastapi import FastAPI, Request, HTTPException
from aiogram.types import Update

from app.bot import bot, dp


logging.basicConfig(level=logging.INFO)

app = FastAPI()

PUBLIC_URL = os.getenv("PUBLIC_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "perfume-bot-secret")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"


@app.get("/")
async def home():
    return {
        "status": "Perfume bot FastAPI is running",
        "public_url": PUBLIC_URL,
        "webhook_path": WEBHOOK_PATH,
    }


@app.get("/set-webhook")
async def set_webhook():
    if not PUBLIC_URL:
        raise HTTPException(status_code=500, detail="PUBLIC_URL is not set")

    webhook_url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    info = await bot.get_webhook_info()

    return {
        "status": "webhook set",
        "webhook_url": webhook_url,
        "telegram_webhook_info": info.model_dump(),
    }


@app.get("/webhook-info")
async def webhook_info():
    info = await bot.get_webhook_info()
    return info.model_dump()


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
    except Exception as e:
        logging.exception("Webhook error")
        return {"ok": False, "error": str(e)}

