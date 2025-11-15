import os
import json
import google.generativeai as genai
from google.generativeai import types 
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# 0. Загрузка секретов
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY не найден. Проверьте .env файл.")
    
# 1. Конфигурация Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash') 

chat_sessions = {} 

# 2. Настройка Flask, SocketIO и LoginManager
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "fallback_secret_key") 

# ИСПРАВЛЕНИЕ: Добавляем cors_allowed_origins="*" для Cloud Shell
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*") 

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 3. Модель пользователя (для Flask-Login)
class AdminUser(UserMixin):
    def __init__(self, id):
        self.id = id
        self.username = ADMIN_USER
    def check_password(self, password):
        return password == ADMIN_PASS

admin_db = {"1": AdminUser("1")}

@login_manager.user_loader
def load_user(user_id):
    return admin_db.get(user_id)

# 4. Схемы для структурированного вывода

# Схема для ИИ-карточки (Structured AI Response Schema)
ai_card_schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "description": "Краткое, емкое резюме ответа (2-3 предложения)."},
        "facts": {
            "type": "array",
            "description": "Три наиболее важных факта или ключевых пункта по запросу.",
            "items": {"type": "string"}
        },
        "source_confidence": {"type": "string", "description": "Оценка уверенности ИИ в предоставленной информации (Высокая, Средняя, Низкая)."}
    },
    "required": ["summary", "facts", "source_confidence"]
}

# 5. Маршруты (Страницы)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/gemini')
def gemini_page():
    return render_template('gemini.html')

@app.route('/search')
def search():
    query = request.args.get('q')
    if not query:
        return redirect(url_for('index'))

    # --- 1. Вкладка "Поиск" (Стабильный Markdown промпт) ---
    search_results_text = "Ошибка генерации результатов поиска."
    try:
        prompt_web = (f"Вы — поисковая система. "
                      f"Сгенерируй 5-7 релевантных результатов поиска по запросу: '{query}'. "
                      f"Для каждого результата напиши Заголовок (жирным), Сниппет (краткое описание) и URL (просто текстом). "
                      f"Ответь в виде списка Markdown.")
        
        response_web = model.generate_content(prompt_web)
        search_results_text = response_web.text
    except Exception as e:
        print(f"Ошибка Gemini Web Search: {e}")
        search_results_text = f"Ошибка Gemini API: {e}"
    
    
    # --- 2. Вкладка "ИИ" (Структурированный JSON-ответ для карточки) ---
    ai_result = "Ошибка ИИ"
    ai_card_data = None
    try:
        prompt_ai_card = (f"Проанализируй запрос: '{query}'. "
                          f"Сгенерируй структурированный ответ, который можно использовать для карточки-саммари.")
        
        response_ai = model.generate_content(
            prompt_ai_card,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ai_card_schema)
        )
        ai_result = response_ai.text 
        ai_card_data = json.loads(response_ai.text)
    except Exception as e:
        print(f"Ошибка Gemini AI Card: {e}")
        ai_result = f'Ошибка Gemini API. Не удалось получить JSON-ответ. Детали: {e}'
        ai_card_data = None

    # --- 3. Вкладка "Официальный сайт" ---
    site_result = "Не найден"
    try:
        prompt_site = (f"Какой официальный домен верхнего уровня (например, 'google.com' или 'apple.com') "
                       f"для запроса: '{query}'. "
                       f"Ответь ТОЛЬКО ОДНИМ ДОМЕНОМ и больше ничем. Если не уверен, напиши 'Не найден'.")
        response_site = model.generate_content(prompt_site)
        site_result = response_site.text.strip().replace("`", "")
    except Exception as e:
        site_result = f"Ошибка Gemini API: {e}"


    return render_template('results.html', 
                           query=query,
                           ai_response_json=ai_result, 
                           ai_card_data=ai_card_data, 
                           official_site=site_result,
                           search_results=search_results_text)

# 6. Маршруты Админ-панели (без изменений)
# (Маршруты /login, /admin, /logout без изменений)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_to_login = admin_db.get("1") if username == ADMIN_USER else None
        if user_to_login and user_to_login.check_password(password):
            login_user(user_to_login)
            return redirect(url_for('admin'))
        else:
            flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# 7. Real-time Cобытия (SocketIO)

@socketio.on('connect')
def handle_connect():
    global chat_sessions
    if request.sid not in chat_sessions:
        chat_sessions[request.sid] = model.start_chat()

@socketio.on('disconnect')
def handle_disconnect():
    global chat_sessions
    if request.sid in chat_sessions:
        del chat_sessions[request.sid]

@socketio.on('send_gemini_message')
def handle_gemini_message(data):
    message = data.get('message')
    client_sid = request.sid
    if client_sid not in chat_sessions or not message:
        emit('receive_gemini_message', {'user': 'Система', 'text': 'Ошибка: Сессия чата не найдена.'})
        return
    chat = chat_sessions[client_sid]
    try:
        response = chat.send_message(message)
        emit('receive_gemini_message', {'user': 'Gemini', 'text': response.text})
    except Exception as e:
        error_message = f"Произошла ошибка API: {e}"
        emit('receive_gemini_message', {'user': 'Ошибка', 'text': error_message})

@socketio.on('toggle_disco_event')
@login_required
def handle_disco(data):
    emit('disco_update', {'active': data['active']}, broadcast=True)

@socketio.on('send_admin_message_event')
@login_required
def handle_admin_message(data):
    message = data.get('message')
    if message:
        emit('admin_message_broadcast', {'message': message}, broadcast=True)

# 8. Запуск
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)