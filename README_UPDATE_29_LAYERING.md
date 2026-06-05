# Perfume bot update: 29 perfumes + time/season + layering

Replace your project files with this folder or copy these files:

- app/data/perfumes.py
- app/services/recommender.py
- app/services/layering.py
- app/keyboards.py
- app/states.py
- app/bot.py
- main.py
- requirements.txt

For Vercel, use `main.py` and set environment variables:

```env
BOT_TOKEN=your_new_token
OWNER_ID=your_telegram_id
PUBLIC_URL=https://your-project.vercel.app
WEBHOOK_SECRET=your_secret
```

After deploy open:

```text
https://your-project.vercel.app/set-webhook
```

For local polling run:

```bash
python run_polling.py
```
