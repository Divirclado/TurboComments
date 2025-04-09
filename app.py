from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'ogg', 'pdf', 'ppt', 'pptx', 'doc', 'docx'}

# URL de conexión PostgreSQL proporcionada por Render
DATABASE_URL = os.getenv('DATABASE_URL', 'postgres://usuario:contraseña@servidor:puerto/nombre_base')

# Conectar a la base de datos
def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    return conn

# Crear tablas en PostgreSQL
def create_tables():
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id SERIAL PRIMARY KEY,
                    text TEXT NOT NULL,
                    file_path TEXT,
                    likes INTEGER DEFAULT 0,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS replies (
                    id SERIAL PRIMARY KEY,
                    comment_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    comment_id INTEGER NOT NULL,
                    UNIQUE(user_id, comment_id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (comment_id) REFERENCES comments(id)
                )
            ''')
            conn.commit()
            print("Tablas creadas exitosamente.")

# Inicializar la base de datos al inicio
create_tables()

# Rutas de registro, login, index, etc.
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        with get_db() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)', (username, password))
                    conn.commit()
                    return redirect(url_for('login'))
                except psycopg2.IntegrityError:
                    return "El nombre de usuario ya existe."
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
                if user and check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    return redirect(url_for('index'))
                else:
                    return "Usuario o contraseña incorrectos."
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Lógica para comentarios, likes, etc.
        pass

    # Recuperar comentarios y respuestas
    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT comments.id, comments.text, comments.file_path, comments.likes, users.username
                FROM comments
                JOIN users ON comments.user_id = users.id
            ''')
            comments = cursor.fetchall()
    return render_template('index.html', comments=comments, username=session['username'])

if __name__ == '__main__':
    app.run(debug=True)