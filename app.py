from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
import os
import hashlib
import secrets

app = Flask(__name__)
app.secret_key = "zenge_secret_realm_key_2024"

ADMIN_EMAIL = "aibelshibin7@gmail.com"
ADMIN_PASSWORD = "123456goodd"

DB_NAME = "database.db"

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            plain_password TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            game_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    # Migration: add plain_password column if upgrading from old DB
    try:
        c.execute("ALTER TABLE users ADD COLUMN plain_password TEXT NOT NULL DEFAULT ''")
        conn.commit()
    except:
        pass
    conn.close()

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("welcome"))
    return render_template("index.html", error=None)

@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not email or not password:
        return render_template("index.html", error="Please fill in all fields.")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, password_hash, salt FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    if not user:
        return render_template("index.html", error="No account found with that email.")
    hashed, _ = hash_password(password, user[2])
    if hashed != user[1]:
        return render_template("index.html", error="Incorrect password.")
    session["user_id"] = user[0]
    session["user_email"] = email
    return redirect(url_for("welcome"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", error=None)
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not email or not password or not confirm:
        return render_template("register.html", error="Please fill in all fields.")
    if "@" not in email or "." not in email:
        return render_template("register.html", error="Please enter a valid email address.")
    if len(password) < 6:
        return render_template("register.html", error="Password must be at least 6 characters.")
    if password != confirm:
        return render_template("register.html", error="Passwords do not match.")
    hashed, salt = hash_password(password)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (email, password_hash, salt, plain_password) VALUES (?, ?, ?, ?)", (email, hashed, salt, password))
        conn.commit()
        user_id = c.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("register.html", error="An account with that email already exists.")
    conn.close()
    session["user_id"] = user_id
    session["user_email"] = email
    return redirect(url_for("welcome"))

@app.route("/welcome")
def welcome():
    if not session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("welcome.html", email=session["user_email"])

@app.route("/game")
def game():
    if not session.get("user_id") and not session.get("logged_in"):
        return redirect(url_for("home"))
    return render_template("game.html")

@app.route("/games")
def games():
    if not session.get("user_id") and not session.get("logged_in"):
        return redirect(url_for("home"))
    user_id = session.get("user_id")
    scores = {}
    if user_id:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT game_id, MAX(score) FROM scores WHERE user_id = ? GROUP BY game_id", (user_id,))
        for row in c.fetchall():
            scores[row[0]] = row[1]
        conn.close()
    return render_template("games.html", email=session.get("user_email", "Warden"), scores=scores)

@app.route("/save_score", methods=["POST"])
def save_score():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False})
    data = request.get_json()
    game_id = data.get("game_id")
    score = int(data.get("score", 0))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO scores (user_id, game_id, score) VALUES (?, ?, ?)", (user_id, game_id, score))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        return render_template("login.html", error="Wrong credentials.")
    return render_template("login.html", error=None)

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("admin_login"))
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, email, plain_password, created_at FROM users ORDER BY id DESC")
    users = c.fetchall()
    c.execute("""
        SELECT u.email, s.game_id, MAX(s.score)
        FROM scores s JOIN users u ON s.user_id = u.id
        GROUP BY s.user_id, s.game_id
        ORDER BY MAX(s.score) DESC
    """)
    top_scores = c.fetchall()
    conn.close()
    return render_template("dashboard.html", items=users, top_scores=top_scores)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
