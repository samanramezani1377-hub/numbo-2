# نومبو ۲ (Numbo-2)

کراولر سبک، پایدار و **اجرای مداوم** برای استخراج اطلاعات تماس عمومی از وب‌سایت‌ها.

طراحی شده برای اجرا روی هاست لینوکس. استخراج شماره تماس (فرمت‌های ایرانی)، ایمیل، نام کسب‌وکار و دسته‌بندی نتایج.

## ویژگی‌های اصلی

- **اجرای مداوم** تا زمانی که خودت با Ctrl+C یا SIGTERM متوقفش کنی
- استخراج شماره موبایل و ثابت ایرانی + بین‌المللی
- استخراج ایمیل و لینک شبکه‌های اجتماعی
- حذف تکراری خودکار
- دسته‌بندی ساده بر اساس کلیدواژه و تشخیص شهر
- **فیلتر قابل تنظیم دامنه (TLD)** — پیش‌فرض فقط `.ir`
- ذخیره در SQLite + خروجی CSV و Excel
- احترام به robots.txt + Rate Limit + AutoThrottle
- چرخش User-Agent
- آماده اجرا با یک دستور

## پیش‌نیاز

- Python 3.10+
- لینوکس (Ubuntu / Debian / CentOS و ...)

## نصب سریع

```bash
git clone https://github.com/samanramezani1377-hub/numbo-2.git
cd numbo-2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## تنظیم فیلتر دامنه (فقط .ir یا هر چیز دیگه)

فایل `numbo/settings.py` را باز کن و این بخش را تغییر بده:

```python
# فقط دامنه‌های ایرانی
ALLOWED_TLDS = [".ir"]

# یا همه دامنه‌ها (بدون محدودیت)
# ALLOWED_TLDS = []

# یا چند پسوند
# ALLOWED_TLDS = [".ir", ".com", ".org"]
```

پیش‌فرض روی فقط `.ir` تنظیم شده است.

## نحوه اجرا (مداوم)

1. دامنه‌ها یا URLهای اولیه را در فایل `seeds.txt` بنویس (هر خط یکی):

```text
example.ir
some-shop.ir
https://www.another.ir
```

2. اجرا:

```bash
python run.py
```

کراولر شروع می‌کند و بعد از هر دور کامل، چند دقیقه صبر می‌کند و دوباره از اول شروع می‌کند. تا وقتی که Ctrl+C نزنی یا سرویس را متوقف نکنی، ادامه می‌دهد.

برای اجرا در پس‌زمینه روی سرور:

```bash
nohup python run.py > numbo.log 2>&1 &
```

یا با systemd (نمونه سرویس در `deploy/numbo.service`).

## خروجی گرفتن

```bash
python export.py
```

فایل‌های CSV و Excel در پوشه `data/` ساخته می‌شوند.

## ساختار پروژه

```
numbo-2/
├── run.py                 # اجرای مداوم
├── export.py              # خروجی CSV/Excel
├── seeds.txt              # لیست شروع
├── requirements.txt
├── numbo/
│   ├── settings.py        # تنظیمات (از جمله ALLOWED_TLDS)
│   ├── items.py
│   ├── pipelines.py
│   ├── middlewares.py
│   ├── spiders/contact.py
│   └── utils/
│       ├── phone.py
│       └── category.py
└── deploy/
    └── numbo.service
```

## نکات مهم

- به `robots.txt` احترام گذاشته می‌شود.
- تأخیر و محدودیت همزمانی برای جلوگیری از فشار روی سایت‌ها تنظیم شده.
- این ابزار فقط برای اطلاعات **عمومی** طراحی شده است.
- مسئولیت استفاده از داده‌ها بر عهده کاربر است.

---

ساخته‌شده از صفر با تمرکز روی سادگی، پایداری و نگهداری راحت.
