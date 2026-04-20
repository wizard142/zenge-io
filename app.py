from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import sqlite3
import os
import hashlib
import secrets
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "zenge_secret_realm_key_2024"

# ── ADMIN CREDENTIALS ──
ADMIN_EMAIL    = "aibelshibin7@gmail.com"
ADMIN_PASSWORD = "123456goodd"

# ── GMAIL SMTP CONFIG ──
# To set this up:
# 1. Go to your Gmail account → Settings → Security
# 2. Enable 2-Step Verification if not already on
# 3. Go to Security → App Passwords
# 4. Create a new App Password (select "Mail" + "Windows Computer")
# 5. Paste the 16-character code as SMTP_PASSWORD below
SMTP_EMAIL    = "aibelshibin7@gmail.com"   # your Gmail address
SMTP_PASSWORD = "lhbw btfi unxl ocrs"   # 16-char Gmail App Password
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

DB_NAME = "database.db"

# ════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt

def send_verification_email(to_email, code):
    """Send a 6-digit verification code to the user's email."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Zenge — Verify Your Account"
        msg["From"]    = SMTP_EMAIL
        msg["To"]      = to_email

        body = f"""
        <html><body style="background:#07080f;color:#e8dfc8;font-family:'Courier New',monospace;padding:40px">
          <div style="max-width:480px;margin:0 auto;background:#0c0e1a;border:2px solid rgba(200,168,75,0.3);padding:40px">
            <div style="font-size:28px;font-weight:700;color:#c8a84b;letter-spacing:0.2em;margin-bottom:8px">ZENGE</div>
            <div style="font-size:12px;color:#5c5542;letter-spacing:0.3em;text-transform:uppercase;margin-bottom:32px">Realm of Souls</div>
            <div style="font-size:15px;color:#a09070;margin-bottom:24px">Your verification code is:</div>
            <div style="font-size:42px;font-weight:700;color:#c8a84b;letter-spacing:0.3em;background:#07080f;padding:20px;text-align:center;border:1px solid rgba(200,168,75,0.2);margin-bottom:24px">{code}</div>
            <div style="font-size:12px;color:#5c5542;line-height:1.8">
              Enter this code on the verification page to complete your registration.<br>
              This code expires in <strong style="color:#c8a84b">10 minutes</strong>.<br><br>
              If you didn't create an account, ignore this email.
            </div>
          </div>
        </body></html>
        """
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

# ════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Users — verified accounts only
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            plain_password TEXT NOT NULL DEFAULT '',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Pending registrations awaiting email verification
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            email         TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            plain_password TEXT NOT NULL,
            code          TEXT NOT NULL,
            expires_at    TIMESTAMP NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Scores
    c.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            game_id    TEXT NOT NULL,
            score      INTEGER NOT NULL,
            played_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()

    # Migrations for existing DBs
    for col in [("users", "plain_password", "TEXT NOT NULL DEFAULT ''")]:
        try:
            c.execute(f"ALTER TABLE {col[0]} ADD COLUMN {col[1]} {col[2]}")
            conn.commit()
        except:
            pass

    conn.close()

def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ════════════════════════════════════════════
# ROUTES — AUTH
# ════════════════════════════════════════════

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("welcome"))
    return render_template("index.html", error=None)

# ── LOGIN ──
@app.route("/login", methods=["POST"])
def login():
    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("index.html", error="Please fill in all fields.")

    conn = db()
    user = conn.execute(
        "SELECT id, password_hash, salt FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()

    if not user:
        return render_template("index.html", error="No account found with that email.")

    hashed, _ = hash_password(password, user["salt"])
    if hashed != user["password_hash"]:
        return render_template("index.html", error="Incorrect password.")

    session["user_id"]    = user["id"]
    session["user_email"] = email
    return redirect(url_for("welcome"))

# ── REGISTER — Step 1: collect details, send code ──
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", error=None)

    email   = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm", "")

    # Validation
    if not email or not password or not confirm:
        return render_template("register.html", error="Please fill in all fields.")
    if "@" not in email or "." not in email.split("@")[-1]:
        return render_template("register.html", error="Please enter a valid email address.")
    if len(password) < 6:
        return render_template("register.html", error="Password must be at least 6 characters.")
    if password != confirm:
        return render_template("register.html", error="Passwords do not match.")

    # Check if already a full user
    conn = db()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if existing:
        return render_template("register.html", error="An account with that email already exists.")

    # Generate 6-digit code
    code = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    hashed, salt = hash_password(password)

    # Store pending registration (delete old ones for same email first)
    conn = db()
    conn.execute("DELETE FROM pending_users WHERE email = ?", (email,))
    conn.execute(
        "INSERT INTO pending_users (email, password_hash, salt, plain_password, code, expires_at) VALUES (?,?,?,?,?,?)",
        (email, hashed, salt, password, code, expires)
    )
    conn.commit()
    conn.close()

    # Send email
    sent = send_verification_email(email, code)
    if not sent:
        return render_template("register.html",
            error="Failed to send verification email. Check your SMTP settings in app.py.")

    # Store email in session for the verify step
    session["pending_email"] = email
    return redirect(url_for("verify"))

# ── REGISTER — Step 2: enter the verification code ──
@app.route("/verify", methods=["GET", "POST"])
def verify():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("register"))

    if request.method == "GET":
        return render_template("verify.html", email=email, error=None)

    code_input = request.form.get("code", "").strip()

    conn = db()
    pending = conn.execute(
        "SELECT * FROM pending_users WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()
    conn.close()

    if not pending:
        return render_template("verify.html", email=email, error="No pending registration found. Please register again.")

    # Check expiry
    expires = datetime.strptime(pending["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires:
        return render_template("verify.html", email=email,
            error="Verification code has expired. Please register again.")

    if code_input != pending["code"]:
        return render_template("verify.html", email=email, error="Incorrect code. Check your email and try again.")

    # Code is correct — create the real user account
    conn = db()
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash, salt, plain_password) VALUES (?,?,?,?)",
            (email, pending["password_hash"], pending["salt"], pending["plain_password"])
        )
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("DELETE FROM pending_users WHERE email = ?", (email,))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return render_template("verify.html", email=email,
            error="An account with that email already exists.")
    conn.close()

    session.pop("pending_email", None)
    session["user_id"]    = user_id
    session["user_email"] = email
    return redirect(url_for("welcome"))

# ── RESEND CODE ──
@app.route("/resend_code", methods=["POST"])
def resend_code():
    email = session.get("pending_email")
    if not email:
        return redirect(url_for("register"))

    conn = db()
    pending = conn.execute(
        "SELECT * FROM pending_users WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email,)
    ).fetchone()

    if not pending:
        conn.close()
        return redirect(url_for("register"))

    # Generate new code and reset expiry
    code    = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE pending_users SET code=?, expires_at=? WHERE email=?",
        (code, expires, email)
    )
    conn.commit()
    conn.close()

    send_verification_email(email, code)
    return render_template("verify.html", email=email, error=None,
                           success="A new code has been sent to your email.")

# ════════════════════════════════════════════
# ROUTES — GAME
# ════════════════════════════════════════════

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
        conn = db()
        rows = conn.execute(
            "SELECT game_id, MAX(score) FROM scores WHERE user_id=? GROUP BY game_id",
            (user_id,)
        ).fetchall()
        conn.close()
        for row in rows:
            scores[row[0]] = row[1]
    return render_template("games.html",
                           email=session.get("user_email", "Warden"),
                           scores=scores)

@app.route("/save_score", methods=["POST"])
def save_score():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False})
    data    = request.get_json()
    game_id = data.get("game_id")
    score   = int(data.get("score", 0))
    conn = db()
    conn.execute(
        "INSERT INTO scores (user_id, game_id, score) VALUES (?,?,?)",
        (user_id, game_id, score)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ════════════════════════════════════════════
# ROUTES — ADMIN
# ════════════════════════════════════════════

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email    = request.form.get("email")
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
    conn = db()
    users = conn.execute(
        "SELECT id, email, plain_password, created_at FROM users ORDER BY id DESC"
    ).fetchall()
    top_scores = conn.execute("""
        SELECT u.email, s.game_id, MAX(s.score)
        FROM scores s JOIN users u ON s.user_id = u.id
        GROUP BY s.user_id, s.game_id
        ORDER BY MAX(s.score) DESC
    """).fetchall()
    conn.close()
    return render_template("dashboard.html", items=users, top_scores=top_scores)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
