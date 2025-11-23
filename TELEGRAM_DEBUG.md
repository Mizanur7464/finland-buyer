# 🔍 Telegram Bot Debug Guide

## ❌ Bot Reply করছে না?

### ✅ Step-by-Step Fix:

#### **1. .env ফাইল Check করুন:**

```env
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

#### **2. Token Verify করুন:**

Browser-এ যান:
```
https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

এই response আসা উচিত:
```json
{
  "ok": true,
  "result": {
    "id": 123456789,
    "is_bot": true,
    "first_name": "Your Bot Name"
  }
}
```

#### **3. Chat ID Verify করুন:**

1. Bot-এ **যেকোনো message** পাঠান (যেমন: "hi")
2. Browser-এ যান:
```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```
3. Response-এ `"chat":{"id":123456789}` খুঁজুন
4. এই number `.env` ফাইলের `TELEGRAM_CHAT_ID`-এ আছে কিনা check করুন

#### **4. Bot Restart করুন:**

```bash
python main.py
```

Terminal-এ দেখবেন:
```
✅ Telegram bot started
📱 Bot is ready. Chat ID: xxx
📱 Bot is listening for commands...
📨 Received /start command
✅ Replied to /start command from chat xxx
```

#### **5. Telegram-এ Test করুন:**

1. Bot-এ `/start` পাঠান
2. Terminal-এ `📨 Received /start command` দেখবেন
3. Telegram-এ bot reply করবে

---

## ⚠️ Common Issues:

### **Issue 1: Bot Reply করছে না**
→ Chat ID সঠিক নয়
→ Solution: Chat ID verify করুন (step 3)

### **Issue 2: "Could not send startup message"**
→ Token বা Chat ID ভুল
→ Solution: Token & Chat ID verify করুন

### **Issue 3: Terminal-এ "Received" দেখছেন কিন্তু reply নেই**
→ Handler error আছে
→ Solution: Terminal-এ error message check করুন

---

**এখন try করুন!** 🚀

