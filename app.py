from flask import Flask, render_template, request, redirect, url_for, session, g
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['DATABASE'] = 'comments.db'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'ogg', 'pdf', 'ppt', 'pptx', 'doc', 'docx'}

# Función para conectar a la base de datos
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
    return db

# Crear tablas en la base de datos
def create_tables():
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

# Crear tabla para likes únicos
def create_likes_table():
    with sqlite3.connect(app.config['DATABASE']) as conn:
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
        print("Tabla 'likes' creada (si no existía).")

# Llamar a las funciones para crear las tablas necesarias
create_tables()
create_likes_table()

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
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
        if 'comment' in request.form:  # Añadir un comentario
            comment = request.form.get('comment')
            file = request.files.get('file')
            file_path = None
            if file and '.' in file.filename:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
            with get_db() as conn:
                conn.execute('INSERT INTO comments (text, file_path, user_id) VALUES (?, ?, ?)',
                             (comment, file_path, session['user_id']))
        elif 'like' in request.form:  # Dar like
            comment_id = request.form.get('like')
            with get_db() as conn:
                try:
                    # Insertar el like en la tabla likes
                    conn.execute('INSERT INTO likes (user_id, comment_id) VALUES (?, ?)', 
                                 (session['user_id'], comment_id))
                    # Incrementar el contador de likes
                    conn.execute('UPDATE comments SET likes = likes + 1 WHERE id = ?', (comment_id,))
                except sqlite3.IntegrityError:
                    return "Ya diste like a este comentario.", 403
        elif 'delete' in request.form:  # Eliminar comentario
            comment_id = request.form.get('delete')
            with get_db() as conn:
                comment = conn.execute('SELECT user_id FROM comments WHERE id = ?', (comment_id,)).fetchone()
                if comment and comment[0] == session['user_id']:
                    conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
                else:
                    return "No puedes eliminar este comentario, no te pertenece.", 403
        elif 'reply' in request.form:  # Responder comentario
            reply = request.form.get('reply')
            comment_id = request.form.get('comment_id')
            with get_db() as conn:
                conn.execute('INSERT INTO replies (comment_id, text, user_id) VALUES (?, ?, ?)',
                             (comment_id, reply, session['user_id']))

    # Recuperar comentarios y respuestas
    with get_db() as conn:
        comments = conn.execute('''
            SELECT comments.id, comments.text, comments.file_path, comments.likes, users.username, comments.user_id
            FROM comments
            JOIN users ON comments.user_id = users.id
        ''').fetchall()
        replies = conn.execute('''
            SELECT replies.comment_id, replies.text, users.username
            FROM replies
            JOIN users ON replies.user_id = users.id
        ''').fetchall()

    return render_template('index.html', comments=comments, replies=replies, username=session['username'])

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

if __name__ == '__main__':
    app.run(debug=True)