# ETN × RAPIRA ONLINE — запуск на Bothost + Netlify

В проекте есть Telegram Mini App (папка `netlify-deploy`), Flask API и Telegram-бот с `/start` и `/help` (папка `bothost-backend`). Это подготовленный пакет, но он **не станет онлайн автоматически**: нужны ваши настройки и развёртывание в аккаунтах Bothost, Netlify и Telegram.

## 1. Опубликуйте сайт на Netlify
1. Загрузите папку `netlify-deploy` в свой Git-репозиторий и подключите его к Netlify (или разверните папку как статический сайт).
2. Скопируйте выданный Netlify HTTPS URL, Ваш сайт: **https://etntest8237.netlify.app**. Этот адрес уже прописан как адрес кнопки в Telegram-боте; если в Bothost задана переменная `WEBAPP_URL`, убедитесь, что в ней стоит тот же адрес.

## 2. Разверните API на Bothost
1. Создайте Python web service из содержимого `bothost-backend`.
2. Установите зависимости из `requirements.txt`.
3. Команда запуска web-сервиса: `gunicorn --workers 2 --bind 0.0.0.0:$PORT app:app`
4. В переменных окружения сервиса задайте:
   - `BOT_TOKEN` — токен от BotFather (секрет, только в панели хостинга).
   - `ADMIN_IDS` — ваш Telegram numeric user ID.
   - `WEBAPP_URL` — HTTPS URL Netlify.
   - `ETN_DB_PATH` — путь к постоянному диску, например `/data/etn.sqlite3`.
5. Подключите persistent disk и проверьте `https://ВАШ_API_ДОМЕН/health`. Должен вернуться JSON с `"ok": true`.

## 3. Запустите Telegram-бота постоянно
Создайте отдельный always-on worker/background service на Bothost из той же папки `bothost-backend`, с командой `python bot.py`. Укажите ему те же `BOT_TOKEN` и `WEBAPP_URL`. Если ваш тариф Bothost не поддерживает фоновые worker-процессы, используйте отдельный постоянный Python service; не запускайте два polling-процесса с одним токеном одновременно.

## 4. Свяжите Netlify с API
Откройте `netlify-deploy/netlify.toml` и замените `https://YOUR-BOTHOST-API-DOMAIN` на реальный HTTPS-домен вашего API. Затем заново опубликуйте Netlify. Без этого адреса API функции сайта, которым нужен сервер, не заработают.

## 5. Проверка
- `https://ВАШ_API_ДОМЕН/health` отвечает `ok: true`.
- Напишите боту `/start`; он должен показать кнопку открытия приложения.
- Откройте приложение через кнопку внутри Telegram, а не обычной вкладкой браузера.
- Проверьте `/api/me` внутри Telegram Mini App.

## Важно
- Не присылайте `BOT_TOKEN` в чат и не добавляйте его в HTML/репозиторий. Храните его только в переменных окружения Bothost.
- Если токен уже публиковался, отзовите его через BotFather и создайте новый.
- Наличие файлов не означает, что приложение уже онлайн. Для запуска нужны настройки и развёртывание в ваших аккаунтах.
- Backend использует проверку Telegram WebApp `initData` для `/api/*`. Некоторые старые функции интерфейса пока используют `localStorage`, поэтому не все разделы синхронизируются между пользователями.


### Администраторы Telegram
В переменных окружения Bothost задайте `ADMIN_USERNAMES=wtfskyred,kirill_sarychev11,d3ffolter` (без символов `@`). Сервер проверяет эти имена по подписанным Telegram WebApp initData. Также можно указать числовые Telegram ID через `ADMIN_IDS` для более устойчивой привязки, поскольку username может измениться. После изменения переменных перезапустите веб-сервис.
