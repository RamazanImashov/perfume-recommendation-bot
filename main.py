import os

from fastapi import FastAPI, Request, HTTPException
from aiogram.types import Update

from app.bot import bot, dp


app = FastAPI()

PUBLIC_URL = os.getenv("PUBLIC_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "perfume-bot-secret")
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"


@app.get("/")
async def home():
    return {"status": "Perfume bot is running"}


@app.get("/set-webhook")
async def set_webhook():
    if not PUBLIC_URL:
        raise HTTPException(status_code=500, detail="PUBLIC_URL is not set")

    webhook_url = f"{PUBLIC_URL}{WEBHOOK_PATH}"

    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
    )

    return {
        "status": "webhook set",
        "webhook_url": webhook_url,
    }


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)

    return {"ok": True}