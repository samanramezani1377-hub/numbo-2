# نومبو ۲

کراولر + پنل وب. نصب روی هاست لینوکس با یک دستور. بعد همه کار از پنل وب.

## نصب ساده (هاست لینوکس)

CI هر بار تست می‌گیرد و فایل `numbo-2.zip` را در بخش Releases می‌سازد.

روی سرور:

```bash
curl -L -o numbo-2.zip https://github.com/samanramezani1377-hub/numbo-2/releases/latest/download/numbo-2.zip
unzip numbo-2.zip -d numbo && cd numbo
sudo bash install.sh
```

خروجی نصب آدرس پنل و رمز ورود را نشان می‌دهد.

مثال:

```
Panel:    http://YOUR_IP:8080
Password: ....
```

برو همان آدرس. از پنل:

- دامنه‌ها را بنویس
- فیلتر `.ir` را تنظیم کن
- کراول را شروع / توقف کن
- نتایج را ببین و Excel بگیر

پنل بعد از ری‌ستارت سرور هم خودکار باقی می‌ماند (systemd).

اگر ریپو private است، zip را از بخش Actions دانلود کن یا با git clone نصب کن:

```bash
git clone https://github.com/samanramezani1377-hub/numbo-2.git
cd numbo-2
sudo bash install.sh
```

## فیچرها

- استخراج شماره / ایمیل / شبکه اجتماعی
- تشخیص وردپرس، ووکامرس و تکنولوژی‌های دیگر
- فیلتر قابل تنظیم `.ir`
- خروجی Excel

فقط اطلاعات عمومی سایت‌ها جمع‌آوری می‌شود.
