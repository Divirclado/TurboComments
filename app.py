from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'ogg', 'pdf', 'ppt', 'pptx', 'doc', 'docx'}

# Obtén la URL de conexión a PostgreSQL desde la variable de entorno
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("Error: DATABASE_URL no se encontró en las variables de entorno. Revisa tu archivo .env.")
    exit()

# Función para conectarse a la base de datos PostgreSQL
def get_db():
    try:
        conn = psycopg2.connect(
            DATABASE_URL,
            sslmode='require',
            cursor_factory=DictCursor
        )
        return conn
    except psycopg2.Error as e:
        print(f"Error al conectar a la base de datos: {e}")
        raise

# Crear tablas en PostgreSQL si no existen
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            print("Tablas creadas exitosamente.")

# Inicializar la base de datos al inicio de la aplicación
try:
    create_tables()
except Exception as e:
    print(f"No se pudieron crear las tablas: {e}")
    exit()

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
        if 'comment' in request.form:
            comment = request.form.get('comment')
            file = request.files.get('file')
            file_path = None
            if file and '.' in file.filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('INSERT INTO comments (text, file_path, user_id) VALUES (%s, %s, %s)',
                                   (comment, file_path, session['user_id']))
                    conn.commit()
        elif 'like' in request.form:
            comment_id = request.form.get('like')
            with get_db() as conn:
                with conn.cursor() as cursor:
                    try:
                        cursor.execute('INSERT INTO likes (user_id, comment_id) VALUES (%s, %s)', 
                                       (session['user_id'], comment_id))
                        cursor.execute('UPDATE comments SET likes = likes + 1 WHERE id = %s', (comment_id,))
                        conn.commit()
                    except psycopg2.IntegrityError:
                        return "Ya diste like a este comentario.", 403
        elif 'delete' in request.form:
            comment_id = request.form.get('delete')
            with get_db() as conn:
                with conn.cursor() as cursor:
                    # Eliminar referencias en la tabla 'likes'
                    cursor.execute('DELETE FROM likes WHERE comment_id = %s', (comment_id,))
                    conn.commit()

                    # Luego elimina el comentario
                    cursor.execute('DELETE FROM comments WHERE id = %s AND user_id = %s', (comment_id, session['user_id']))
                    conn.commit()
        elif 'reply' in request.form:
            reply_text = request.form.get('reply')
            comment_id = request.form.get('comment_id')
            with get_db() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('INSERT INTO replies (comment_id, text, user_id) VALUES (%s, %s, %s)',
                                   (comment_id, reply_text, session['user_id']))
                    conn.commit()

    with get_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT comments.id, comments.text, comments.file_path, comments.likes, users.username, comments.user_id, comments.created_at
                FROM comments
                JOIN users ON comments.user_id = users.id
            ''')
            comments = cursor.fetchall()

            cursor.execute('''
                SELECT replies.comment_id, replies.text, users.username
                FROM replies
                JOIN users ON replies.user_id = users.id
            ''')
            replies = cursor.fetchall()

    return render_template('index.html', comments=comments, replies=replies, username=session['username'])

if __name__ == '__main__':
    app.run(debug=True)