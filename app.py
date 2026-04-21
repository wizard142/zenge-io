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
import json

app = Flask(__name__)
app.secret_key = "zenge_secret_realm_key_2024"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # 1 hour

# ── ADMIN CREDENTIALS ──
ADMIN_EMAIL    = "aibelshibin7@gmail.com"
ADMIN_PASSWORD = "123456goodd"

# ── GMAIL SMTP CONFIG ──
SMTP_EMAIL    = "aibelshibin7@gmail.com"
SMTP_PASSWORD = "lhbw btfi unxl ocrs"
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

# ── DATABASE ──
# Reads DATABASE_URL from Render environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")

# ════════════════════════════════════════════
# DATABASE CONNECTION
# ════════════════════════════════════════════
def db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
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

    # NEW: RPG Saves table for the story RPG
    c.execute("""
        CREATE TABLE IF NOT EXISTS rpg_saves (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) UNIQUE,
            character_name TEXT DEFAULT 'The Wanderer',
            character_class TEXT DEFAULT 'Knight',
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            xp_next INTEGER DEFAULT 100,
            hp INTEGER DEFAULT 50,
            max_hp INTEGER DEFAULT 50,
            mana INTEGER DEFAULT 20,
            max_mana INTEGER DEFAULT 20,
            strength INTEGER DEFAULT 10,
            dexterity INTEGER DEFAULT 10,
            intelligence INTEGER DEFAULT 10,
            gold INTEGER DEFAULT 50,
            chapter INTEGER DEFAULT 1,
            step TEXT DEFAULT 'class_select',
            current_scene TEXT,
            story_flags JSON DEFAULT '{}',
            inventory JSON DEFAULT '["Health Potion", "Health Potion"]',
            equipment JSON DEFAULT '{"weapon": "Rusted Sword", "armor": "Leather Vest", "accessory": null}',
            companions JSON DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
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
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

# ════════════════════════════════════════════
# ROUTES — AUTH
# ════════════════════════════════════════════

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("welcome"))
    return render_template("index.html", error=None)

@app.route("/login", methods=["POST"])
def login():
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
    return redirect(url_for("welcome"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", error=None)

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
    return redirect(url_for("verify") + "?email=" + email)

@app.route("/verify", methods=["GET", "POST"])
def verify():
    # Get email from session OR from query param (fallback for session loss)
    email = session.get("pending_email") or request.args.get("email") or request.form.get("email_hidden","")
    if not email:
        return redirect(url_for("register"))
    # Keep it in session
    session["pending_email"] = email

    if request.method == "GET":
        return render_template("verify.html", email=email, error=None)

    code_input = request.form.get("code", "").strip()

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
def resend_code():
    email = session.get("pending_email") or request.form.get("email_hidden","")
    if not email:
        return redirect(url_for("register"))
    session["pending_email"] = email

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
# ROUTES — STORY RPG
# ════════════════════════════════════════════

@app.route("/story-rpg")
def story_rpg():
    if not session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("story_rpg.html", email=session["user_email"])

@app.route("/api/rpg/save", methods=["POST"])
def save_rpg():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    
    data = request.get_json()
    conn = db()
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO rpg_saves (user_id, character_name, character_class, level, xp, xp_next,
        hp, max_hp, mana, max_mana, strength, dexterity, intelligence, gold, chapter,
        step, current_scene, story_flags, inventory, equipment, companions, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
        character_name = EXCLUDED.character_name,
        character_class = EXCLUDED.character_class,
        level = EXCLUDED.level,
        xp = EXCLUDED.xp,
        xp_next = EXCLUDED.xp_next,
        hp = EXCLUDED.hp,
        max_hp = EXCLUDED.max_hp,
        mana = EXCLUDED.mana,
        max_mana = EXCLUDED.max_mana,
        strength = EXCLUDED.strength,
        dexterity = EXCLUDED.dexterity,
        intelligence = EXCLUDED.intelligence,
        gold = EXCLUDED.gold,
        chapter = EXCLUDED.chapter,
        step = EXCLUDED.step,
        current_scene = EXCLUDED.current_scene,
        story_flags = EXCLUDED.story_flags,
        inventory = EXCLUDED.inventory,
        equipment = EXCLUDED.equipment,
        companions = EXCLUDED.companions,
        updated_at = NOW()
    """, (
        user_id, 
        data.get("character_name", "The Wanderer"),
        data.get("character_class", "Knight"),
        data.get("level", 1),
        data.get("xp", 0),
        data.get("xp_next", 100),
        data.get("hp", 50),
        data.get("max_hp", 50),
        data.get("mana", 20),
        data.get("max_mana", 20),
        data.get("strength", 10),
        data.get("dexterity", 10),
        data.get("intelligence", 10),
        data.get("gold", 50),
        data.get("chapter", 1),
        data.get("step", "class_select"),
        data.get("current_scene", None),
        json.dumps(data.get("story_flags", {})),
        json.dumps(data.get("inventory", ["Health Potion", "Health Potion"])),
        json.dumps(data.get("equipment", {"weapon": "Rusted Sword", "armor": "Leather Vest", "accessory": None})),
        json.dumps(data.get("companions", []))
    ))
    
    conn.commit()
    c.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/rpg/load", methods=["GET"])
def load_rpg():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not logged in"}), 401
    
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM rpg_saves WHERE user_id = %s", (user_id,))
    save = c.fetchone()
    c.close()
    conn.close()
    
    if save:
        # Parse JSON fields
        if save.get("story_flags") and isinstance(save["story_flags"], str):
            save["story_flags"] = json.loads(save["story_flags"])
        if save.get("inventory") and isinstance(save["inventory"], str):
            save["inventory"] = json.loads(save["inventory"])
        if save.get("equipment") and isinstance(save["equipment"], str):
            save["equipment"] = json.loads(save["equipment"])
        if save.get("companions") and isinstance(save["companions"], str):
            save["companions"] = json.loads(save["companions"])
        return jsonify(dict(save))
    return jsonify({"exists": False})

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
    import json
    pw_map = {str(u["id"]): (u["plain_password"] or "") for u in users}
    return render_template("dashboard.html", items=users, top_scores=top_scores, pw_map_json=json.dumps(pw_map))

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