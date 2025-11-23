# 🔧 Telegram Bot Troubleshooting

## ❌ Bot Commands Reply করছে না?

### ✅ Solutions:

#### **1. Check Token & Chat ID:**
- `.env` ফাইলে `TELEGRAM_BOT_TOKEN` সঠিক আছে কিনা check করুন
- `.env` ফাইলে `TELEGRAM_CHAT_ID` সঠিক আছে কিনা check করুন

#### **2. Bot-এ Message পাঠান:**
- আপনার Telegram bot-এ একটি message পাঠান (যেকোনো কিছু)
- তারপর `/start` command দিন
- Bot reply করবে

#### **3. Chat ID সঠিক কিনা Verify করুন:**
1. Bot-এ message পাঠান
2. Browser-এ যান: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Response-এ `"chat":{"id":123456789}` খুঁজুন
4. এই number `.env` ফাইলের `TELEGRAM_CHAT_ID`-এ আছে কিনা check করুন

#### **4. Bot Package Install করুন:**
```bash
pip install python-telegram-bot
```

#### **5. Bot Restart করুন:**
- Ctrl+C চাপুন (stop করুন)
- আবার `python main.py` run করুন

---

## ✅ Working হলে দেখবেন:

Terminal-এ:
```
✅ Telegram bot started
📱 Bot is ready. Chat ID: xxx
📱 Bot is listening for commands...
✅ Processed /start command from xxx
```

Telegram-এ:
- `/start` দিলে bot reply করবে
- `/stats` দিলে stats দেখাবে
- `/status` দিলে status দেখাবে

---

## ⚠️ Common Errors:

### Error: "TELEGRAM_BOT_TOKEN not set"
→ `.env` ফাইলে `TELEGRAM_BOT_TOKEN=your_token` যোগ করুন

### Error: "TELEGRAM_CHAT_ID not set"
→ `.env` ফাইলে `TELEGRAM_CHAT_ID=your_chat_id` যোগ করুন

### Bot reply করছে না
→ Bot-এ প্রথমে একটি message পাঠান, তারপর `/start` দিন

---

**এখন try করুন!** 🚀

