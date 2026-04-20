from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import os
import hashlib
import secrets
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import traceback
from functools import wraps

app = Flask(__name__)
app.secret_key = "zenge_secret_realm_key_2024"
app.config["SESSION_COOKIE_SAMESITE"]  = "Lax"
app.config["SESSION_COOKIE_SECURE"]    = False
app.config["SESSION_COOKIE_HTTPONLY"]  = True
app.config["PERMANENT_SESSION_LIFETIME"] = 3600

# ── ADMIN CREDENTIALS ──
ADMIN_EMAIL    = "aibelshibin7@gmail.com"
ADMIN_PASSWORD = "123456goodd"

# ── GMAIL SMTP CONFIG ──
SMTP_EMAIL    = "aibelshibin7@gmail.com"
SMTP_PASSWORD = "lhbw btfi unxl ocrs"
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

# ════════════════════════════════════════════
# ERROR HANDLING - IMPROVED FOR DEBUGGING
# ════════════════════════════════════════════
logging.basicConfig(level=logging.DEBUG)

def log_errors(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            print(f"[ERROR in {f.__name__}] {str(e)}")
            print(traceback.format_exc())
            # SHOW FULL ERROR IN BROWSER FOR DEBUGGING
            if request.path.startswith('/save_score'):
                return jsonify({"ok": False, "error": str(e)}), 500
            else:
                # Return full error details temporarily for debugging
                error_details = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                return f"<pre>{error_details}</pre>", 500
    return wrapper

# ── DATABASE CONNECTION ──
DATABASE_URL = os.environ.get("DATABASE_URL")

def db():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not set in environment variables")
    
    conn_url = DATABASE_URL
    if 'sslmode' not in conn_url:
        conn_url += '?sslmode=require'
    
    print(f"[DB] Attempting to connect to database...")
    try:
        conn = psycopg2.connect(
            conn_url,
            cursor_factory=RealDictCursor
        )
        print(f"[DB] Connection successful!")
        return conn
    except Exception as e:
        print(f"[DATABASE ERROR] {e}")
        print(traceback.format_exc())
        raise

def init_db():
    conn = None
    try:
        print("[DB] Initializing database...")
        conn = db()
        c = conn.cursor()
        
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                plain_password TEXT NOT NULL DEFAULT '',
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS pending_users (
                id            SERIAL PRIMARY KEY,
                email         TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                plain_password TEXT NOT NULL,
                code          TEXT NOT NULL,
                expires_at    TIMESTAMP NOT NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                id         SERIAL PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                game_id    TEXT NOT NULL,
                score      INTEGER NOT NULL,
                played_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("[DATABASE] Tables created/verified successfully")
        
    except Exception as e:
        print(f"[DATABASE INIT ERROR] {e}")
        print(traceback.format_exc())
        if conn:
            conn.rollback()
    finally:
        if conn:
            c.close()
            conn.close()

# ════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt

def send_verification_email(to_email, code):
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
        print(f"[EMAIL] Verification email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        print(traceback.format_exc())
        return False

# ════════════════════════════════════════════
# ROUTES — AUTH
# ════════════════════════════════════════════

@app.route("/debug-db")
@log_errors
def debug_db():
    try:
        conn = db()
        c = conn.cursor()
        c.execute("SELECT 1 as test, NOW() as current_time")
        result = c.fetchone()
        c.close()
        conn.close()
        return jsonify({
            "status": "ok", 
            "message": "Database connected successfully!",
            "test": result["test"],
            "time": str(result["current_time"])
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "trace": traceback.format_exc()}), 500

@app.route("/")
@log_errors
def home():
    print(f"[ROUTE] Home accessed, session: {session.get('user_id')}")
    if session.get("user_id"):
        return redirect(url_for("welcome"))
    return render_template("index.html", error=None)

@app.route("/login", methods=["POST"])
@log_errors
def login():
    print(f"[ROUTE] Login attempt")
    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("index.html", error="Please fill in all fields.")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, password_hash, salt FROM users WHERE email = %s", (email,))
    user = c.fetchone()
    c.close()
    conn.close()

    if not user:
        return render_template("index.html", error="No account found with that email.")

    hashed, _ = hash_password(password, user["salt"])
    if hashed != user["password_hash"]:
        return render_template("index.html", error="Incorrect password.")

    session["user_id"]    = user["id"]
    session["user_email"] = email
    print(f"[ROUTE] Login successful for {email}")
    return redirect(url_for("welcome"))

@app.route("/register", methods=["GET", "POST"])
@log_errors
def register():
    if request.method == "GET":
        return render_template("register.html", error=None)

    print(f"[ROUTE] Registration attempt")
    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm", "")

    if not email or not password or not confirm:
        return render_template("register.html", error="Please fill in all fields.")
    if "@" not in email or "." not in email.split("@")[-1]:
        return render_template("register.html", error="Please enter a valid email address.")
    if len(password) < 6:
        return render_template("register.html", error="Password must be at least 6 characters.")
    if password != confirm:
        return render_template("register.html", error="Passwords do not match.")

    conn = db()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = %s", (email,))
    existing = c.fetchone()
    c.close()
    conn.close()

    if existing:
        return render_template("register.html", error="An account with that email already exists.")

    code    = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    hashed, salt = hash_password(password)

    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM pending_users WHERE email = %s", (email,))
    c.execute(
        "INSERT INTO pending_users (email, password_hash, salt, plain_password, code, expires_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (email, hashed, salt, password, code, expires)
    )
    conn.commit()
    c.close()
    conn.close()

    sent = send_verification_email(email, code)
    if not sent:
        return render_template("register.html",
            error="Failed to send verification email. Check SMTP settings.")

    session["pending_email"] = email
    session.permanent = True
    print(f"[ROUTE] Registration pending for {email}, code sent")
    return redirect(url_for("verify") + "?email=" + email)

@app.route("/verify", methods=["GET", "POST"])
@log_errors
def verify():
    email = session.get("pending_email") or request.args.get("email") or request.form.get("email_hidden", "")
    if not email:
        return redirect(url_for("register"))
    session["pending_email"] = email
    session.modified = True

    if request.method == "GET":
        return render_template("verify.html", email=email, error=None)

    code_input = request.form.get("code", "").strip()
    print(f"[ROUTE] Verification attempt for {email}")

    conn = db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM pending_users WHERE email = %s ORDER BY created_at DESC LIMIT 1",
        (email,)
    )
    pending = c.fetchone()
    c.close()
    conn.close()

    if not pending:
        return render_template("verify.html", email=email,
            error="No pending registration found. Please register again.")

    expires = datetime.strptime(str(pending["expires_at"])[:19], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires:
        return render_template("verify.html", email=email,
            error="Verification code has expired. Please register again.")

    if code_input != pending["code"]:
        return render_template("verify.html", email=email,
            error="Incorrect code. Check your email and try again.")

    conn = db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (email, password_hash, salt, plain_password) VALUES (%s,%s,%s,%s) RETURNING id",
            (email, pending["password_hash"], pending["salt"], pending["plain_password"])
        )
        user_id = c.fetchone()["id"]
        c.execute("DELETE FROM pending_users WHERE email = %s", (email,))
        conn.commit()
        print(f"[ROUTE] User {email} verified and registered successfully")
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        c.close()
        conn.close()
        return render_template("verify.html", email=email,
            error="An account with that email already exists.")
    c.close()
    conn.close()

    session.pop("pending_email", None)
    session["user_id"]    = user_id
    session["user_email"] = email
    return redirect(url_for("welcome"))

@app.route("/resend_code", methods=["POST"])
@log_errors
def resend_code():
    email = session.get("pending_email") or request.form.get("email_hidden", "")
    if not email:
        return redirect(url_for("register"))
    session["pending_email"] = email
    session.modified = True

    conn = db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM pending_users WHERE email = %s ORDER BY created_at DESC LIMIT 1",
        (email,)
    )
    pending = c.fetchone()

    if not pending:
        c.close()
        conn.close()
        return redirect(url_for("register"))

    code    = str(random.randint(100000, 999999))
    expires = (datetime.utcnow() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "UPDATE pending_users SET code=%s, expires_at=%s WHERE email=%s",
        (code, expires, email)
    )
    conn.commit()
    c.close()
    conn.close()

    send_verification_email(email, code)
    print(f"[ROUTE] New verification code sent to {email}")
    return render_template("verify.html", email=email, error=None,
                           success="A new code has been sent to your email.")

# ════════════════════════════════════════════
# ROUTES — GAME
# ════════════════════════════════════════════

@app.route("/welcome")
@log_errors
def welcome():
    if not session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("welcome.html", email=session["user_email"])

@app.route("/game")
@log_errors
def game():
    if not session.get("user_id") and not session.get("logged_in"):
        return redirect(url_for("home"))
    return render_template("game.html")

@app.route("/games")
@log_errors
def games():
    if not session.get("user_id") and not session.get("logged_in"):
        return redirect(url_for("home"))
    user_id = session.get("user_id")
    scores = {}
    if user_id:
        conn = db()
        c = conn.cursor()
        c.execute(
            "SELECT game_id, MAX(score) FROM scores WHERE user_id=%s GROUP BY game_id",
            (user_id,)
        )
        for row in c.fetchall():
            scores[row["game_id"]] = row["max"]
        c.close()
        conn.close()
    return render_template("games.html",
                           email=session.get("user_email", "Warden"),
                           scores=scores)

@app.route("/save_score", methods=["POST"])
@log_errors
def save_score():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"ok": False})
    data    = request.get_json()
    game_id = data.get("game_id")
    score   = int(data.get("score", 0))
    conn = db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO scores (user_id, game_id, score) VALUES (%s,%s,%s)",
        (user_id, game_id, score)
    )
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"ok": True})

# ════════════════════════════════════════════
# ROUTES — ADMIN
# ════════════════════════════════════════════

@app.route("/admin-login", methods=["GET", "POST"])
@log_errors
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
@log_errors
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("admin_login"))
    conn = db()
    c = conn.cursor()
    c.execute("SELECT id, email, plain_password, created_at FROM users ORDER BY id DESC")
    users = c.fetchall()
    c.execute("""
        SELECT u.email, s.game_id, MAX(s.score)
        FROM scores s JOIN users u ON s.user_id = u.id
        GROUP BY u.email, s.game_id
        ORDER BY MAX(s.score) DESC
    """)
    top_scores = c.fetchall()
    c.close()
    conn.close()
    return render_template("dashboard.html", items=users, top_scores=top_scores)

@app.route("/logout")
@log_errors
def logout():
    session.clear()
    return redirect(url_for("home"))

# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════
if __name__ == "__main__":
    try:
        init_db()
        print("[APP] Database initialized successfully")
    except Exception as e:
        print(f"[WARNING] Could not initialize database: {e}")
        print(traceback.format_exc())
        print("[APP] Continuing startup...")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"[APP] Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)