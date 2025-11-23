# 🖥️ Dashboard চালানোর নিয়ম

## ব্রাউজারে Dashboard দেখার জন্য:

### **Step 1: Dashboard চালান**

নতুন terminal খুলুন এবং run করুন:

```bash
python dashboard/app.py
```

### **Step 2: Browser-এ যান**

Browser-এ এই URL-এ যান:
```
http://localhost:8000
```

### **Step 3: Bot চালান (আরেকটি Terminal-এ)**

আরেকটি terminal-এ bot run করুন:
```bash
python main.py
```

---

## ✅ এখন যা দেখবেন:

Browser-এ Dashboard দেখবেন:
- ✅ Total Copies
- ✅ Successful Copies  
- ✅ Failed Copies
- ✅ Average Latency
- ✅ Real-time Updates (WebSocket)

---

## 💡 Tip:

দুইটি terminal খুলুন:
1. **Terminal 1**: `python dashboard/app.py` (Dashboard)
2. **Terminal 2**: `python main.py` (Bot)

Browser-এ: `http://localhost:8000`

