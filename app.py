import os, json, sqlite3, time, hmac, hashlib
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify, g, send_from_directory
from werkzeug.exceptions import HTTPException

app = Flask(__name__, static_folder="web", static_url_path="/static")
BOT_TOKEN = os.environ.get("8823524687:AAGMTeT1x8c887ppfQJKy9qvkULUxOpjPi4", "").strip()
ADMIN_IDS = {x.strip() for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
ADMIN_USERNAMES = {x.strip().lstrip("@").lower() for x in os.environ.get("ADMIN_USERNAMES", "wtfskyred,kirill_sarychev11,d3ffolter").split(",") if x.strip()}

def is_admin(user):
    """Trust only the Telegram username extracted from verified WebApp initData."""
    return str(user.get("id", "")) in ADMIN_IDS or str(user.get("username", "")).lstrip("@").lower() in ADMIN_USERNAMES
DB_PATH = os.environ.get("ETN_DB_PATH", "/data/etn.sqlite3")
MAX_INITDATA_AGE = int(os.environ.get("MAX_INITDATA_AGE", "86400"))

# State that must be shared between authenticated users.
SHARED_KEYS = {
    "etn_approved_match_stats_v1",
    "etn_match_submissions_v1",
    "etn_organizer_applications_v1",
    "etn_screenshot_registrations_v1",
    "etn_team_rating_v1",
    "etn_support_tickets_v1",
}
# Sensitive global state can only be changed by a Telegram admin.
ADMIN_WRITE_KEYS = {
    "etn_approved_match_stats_v1",
    "etn_demo_accounts_v1",
    "etn_bot_settings_v1",
    "etn_support_tickets_v1",
}
# User-specific keys always remain isolated per Telegram user.
USER_KEYS = {"etn_active_account_v1", "etn_player_profile_v1"}

def connect():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS shared_state (
        key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL, updated_by TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_state (
        user_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, updated_at INTEGER NOT NULL,
        PRIMARY KEY(user_id,key)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY, username TEXT, first_name TEXT, last_seen INTEGER NOT NULL
    )""")
    return c

def verify_init_data(raw):
    if not BOT_TOKEN or not raw:
        return None, "Telegram authentication is not configured"
    try:
        pairs = dict(parse_qsl(raw, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        if not received_hash:
            return None, "Missing Telegram signature"
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated, received_hash):
            return None, "Invalid Telegram signature"
        auth_date = int(pairs.get("auth_date", "0"))
        if auth_date <= 0 or time.time() - auth_date > MAX_INITDATA_AGE or auth_date - time.time() > 60:
            return None, "Telegram session expired; reopen the Mini App"
        user = json.loads(pairs.get("user", "{}"))
        uid = str(user.get("id", ""))
        if not uid:
            return None, "Missing Telegram user"
        return {"id": uid, "username": user.get("username", ""), "first_name": user.get("first_name", "")}, None
    except Exception:
        return None, "Invalid Telegram initData"

@app.before_request
def authenticate():
    # Public website files; API endpoints still require Telegram WebApp authentication.
    if request.path in ("/", "/health") or request.path.startswith("/static/"):
        return None
    raw = request.headers.get("X-Telegram-Init-Data", "")
    user, error = verify_init_data(raw)
    if not user:
        return jsonify({"error": error or "Unauthorized"}), 401
    g.user = user
    c = connect()
    with c:
        c.execute("INSERT INTO users(user_id,username,first_name,last_seen) VALUES(?,?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, last_seen=excluded.last_seen",
                  (user["id"], user["username"], user["first_name"], int(time.time())))
    c.close()

@app.get("/")
def website():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "ETN RAPIRA API", "auth": "Telegram initData required for /api/*"})

@app.get("/api/me")
def me():
    return jsonify({"ok": True, "user": g.user, "is_admin": is_admin(g.user)})

@app.route("/api/state/<path:key>", methods=["GET", "PUT"])
def state(key):
    allowed = SHARED_KEYS | USER_KEYS | {"etn_demo_accounts_v1", "etn_bot_settings_v1"}
    if key not in allowed:
        return jsonify({"error": "Unknown state key"}), 404
    admin_allowed = is_admin(g.user)
    if request.method == "PUT":
        if key in ADMIN_WRITE_KEYS and not admin_allowed:
            return jsonify({"error": "Administrator permission required"}), 403
        body = request.get_json(silent=True) or {}
        if "value" not in body:
            return jsonify({"error": "Missing value"}), 400
        encoded = json.dumps(body["value"], ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 2_000_000:
            return jsonify({"error": "State payload too large (2 MB max)"}), 413
        c = connect()
        with c:
            if key in USER_KEYS or key not in SHARED_KEYS:
                c.execute("INSERT INTO user_state(user_id,key,value,updated_at) VALUES(?,?,?,?) "
                          "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                          (g.user["id"], key, encoded, int(time.time())))
            else:
                c.execute("INSERT INTO shared_state(key,value,updated_at,updated_by) VALUES(?,?,?,?) "
                          "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,updated_by=excluded.updated_by",
                          (key, encoded, int(time.time()), g.user["id"]))
        c.close()
        return jsonify({"ok": True})
    c = connect()
    if key in USER_KEYS or key not in SHARED_KEYS:
        row = c.execute("SELECT value FROM user_state WHERE user_id=? AND key=?", (g.user["id"], key)).fetchone()
    else:
        row = c.execute("SELECT value FROM shared_state WHERE key=?", (key,)).fetchone()
    c.close()
    return jsonify({"found": bool(row), "value": json.loads(row["value"]) if row else None})

@app.get("/api/leaderboard")
def leaderboard():
    c = connect()
    row = c.execute("SELECT value FROM shared_state WHERE key='etn_approved_match_stats_v1'").fetchone()
    c.close()
    return jsonify({"ok": True, "value": json.loads(row["value"]) if row else []})

@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    app.logger.exception("Unhandled API error")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
