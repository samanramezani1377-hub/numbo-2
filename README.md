# نومبو ۲ (Numbo-2)

کراولر سبک، پایدار و **اجرای مداوم** برای استخراج اطلاعات تماس عمومی + تشخیص تکنولوژی سایت‌ها.

طراحی شده برای اجرا روی هاست لینوکس.

## ویژگی‌های اصلی

- **اجرای مداوم** تا زمانی که خودت با Ctrl+C یا SIGTERM متوقفش کنی
- استخراج شماره موبایل و ثابت ایرانی + بین‌المللی
- استخراج ایمیل و لینک شبکه‌های اجتماعی
- **تشخیص تکنولوژی** (WordPress، WooCommerce، Joomla، Drupal، Shopify، Laravel، Next.js، React و ...)
- حذف تکراری خودکار
- دسته‌بندی ساده بر اساس کلیدواژه و تشخیص شهر
- **فیلتر قابل تنظیم دامنه (TLD)** — پیش‌فرض فقط `.ir`
- ذخیره در SQLite + خروجی CSV و Excel
- احترام به robots.txt + Rate Limit + AutoThrottle
- چرخش User-Agent

## تکنولوژی‌هایی که تشخیص می‌دهد

| دسته | تکنولوژی‌ها |
|------|-------------|
| CMS | WordPress, Joomla, Drupal |
| فروشگاهی | WooCommerce, Shopify, Magento, PrestaShop, OpenCart |
| فریمورک | Laravel, Next.js, React, Vue.js, Angular |
| کتابخانه | Bootstrap, jQuery |
| سرویس | Cloudflare, Google Analytics, Google Tag Manager |

هر تشخیص همراه با **سطح اطمینان (confidence)** ذخیره می‌شود.

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

فایل `numbo/settings.py` را باز کن:

```python
# فقط دامنه‌های ایرانی (پیش‌فرض)
ALLOWED_TLDS = [".ir"]

# همه دامنه‌ها
# ALLOWED_TLDS = []

# چند پسوند
# ALLOWED_TLDS = [".ir", ".com"]
```

## نحوه اجرا (مداوم)

1. دامنه‌ها را در `seeds.txt` بنویس:

```text
example.ir
some-shop.ir
```

2. اجرا:

```bash
python run.py
```

تا وقتی Ctrl+C نزنی ادامه می‌دهد.

پس‌زمینه:

```bash
nohup python run.py > numbo.log 2>&1 &
```

## خروجی گرفتن

```bash
python export.py
```

ستون `technologies` در خروجی CSV/Excel شامل تکنولوژی‌های شناسایی‌شده با سطح اطمینان است.

## ساختار پروژه

```
numbo-2/
├── run.py
├── export.py
├── seeds.txt
├── numbo/
│   ├── settings.py          # ALLOWED_TLDS و تنظیمات دیگر
│   ├── spiders/contact.py
│   └── utils/
│       ├── phone.py
│       ├── category.py
│       └── tech.py          # تشخیص تکنولوژی
└── deploy/
    └── numbo.service
```

## نکات مهم

- به `robots.txt` احترام گذاشته می‌شود.
- این ابزار فقط برای اطلاعات **عمومی** طراحی شده است.
- مسئولیت استفاده از داده‌ها بر عهده کاربر است.
