import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, g, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'ogg', 'pdf', 'ppt', 'pptx', 'doc', 'docx'}
app.config['DATABASE'] = '/var/data/comments.db'  # Ruta persistente en Render

# Verifica y crea el archivo de base de datos si no existe
def init_db():
    if not os.path.exists('/var/data'):
        os.makedirs('/var/data')  # Asegura que la carpeta exista
    if not os.path.exists(app.config['DATABASE']):
        with sqlite3.connect(app.config['DATABASE']) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    file_path TEXT,
                    likes INTEGER DEFAULT 0,
                    user_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER,
                    text TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    comment_id INTEGER,
                    UNIQUE(user_id, comment_id), -- Evita que un usuario dé más de un like a un comentario
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (comment_id) REFERENCES comments(id)
                )
            ''')
            print("Base de datos creada exitosamente.")

# Conexión a la base de datos
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Inicializar la base de datos al inicio de la aplicación
init_db()

# Aquí sigue el resto de tus rutas de Flask, como login, register, index, etc.
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        with get_db() as conn:
            try:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                return "El nombre de usuario ya existe."
    return render_template('register.html')

# Más rutas como login, logout, index, etc.

if __name__ == '__main__':
    app.run(debug=True)