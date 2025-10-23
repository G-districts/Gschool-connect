
from flask import Blueprint, request, jsonify
import sqlite3, os, json, time
from ai_classifier import classify, CATEGORIES

ROOT = os.path.dirname(__file__)
DB_PATH = os.path.join(ROOT, "gschool.db")

ai = Blueprint("ai", __name__, url_prefix="/api/ai")

def _db():
    return sqlite3.connect(DB_PATH)

def ensure_schema():
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS categories(
            name TEXT PRIMARY KEY,
            blocked INTEGER DEFAULT 0,
            block_url TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS settings(
            k TEXT PRIMARY KEY,
            v TEXT
        )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS chat_messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            user_id TEXT,
            role TEXT,
            text TEXT,
            ts INTEGER
        )""")
        # seed categories if empty
        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            for c in CATEGORIES:
                cur.execute("INSERT OR IGNORE INTO categories(name, blocked, block_url) VALUES(?,?,?)", (c, 0, None))
        conn.commit()

def get_setting(key, default=None):
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT v FROM settings WHERE k=?", (key,))
        row = cur.fetchone()
        return json.loads(row[0]) if row and row[0] else default

def set_setting(key, value):
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (key, json.dumps(value)))
        conn.commit()

@ai.route("/categories", methods=["GET","POST"])
def categories():
    ensure_schema()
    if request.method == "POST":
        body = request.json or {}
        name = body.get("name")
        blocked = 1 if body.get("blocked") else 0
        block_url = body.get("block_url")
        if not name: return jsonify({"ok":False,"error":"name required"}),400
        with _db() as conn:
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO categories(name, blocked, block_url) VALUES(?,?,?)",
                        (name, blocked, block_url))
            cur.execute("UPDATE categories SET blocked=?, block_url=? WHERE name=?",
                        (blocked, block_url, name))
            conn.commit()
        return jsonify({"ok":True})
    else:
        with _db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name, blocked, block_url FROM categories ORDER BY name")
            rows = [{"name":n,"blocked":bool(b),"block_url":u} for (n,b,u) in cur.fetchall()]
        return jsonify({"ok":True,"categories":rows})

@ai.route("/classify", methods=["POST"])
def api_classify():
    ensure_schema()
    body = request.json or {}
    url = body.get("url") or ""
    html = body.get("html")
    result = classify(url, html)
    # policy
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT blocked, block_url FROM categories WHERE name=?", (result["category"],))
        row = cur.fetchone()
        blocked = bool(row[0]) if row else False
        cat_block_url = row[1] if row else None

    default_redirect = get_setting("blocked_redirect", "https://blocked.gdistrict.org/Gschool%20block")
    final_block_url = cat_block_url or default_redirect
    return jsonify({"ok":True, "url":url, "result":result, "blocked":blocked, "block_url": final_block_url})

# Simple REST chat as a fallback
@ai.route("/chat/send", methods=["POST"])
def chat_send():
    ensure_schema()
    b = request.json or {}
    room = b.get("room") or "*"
    user_id = b.get("user_id") or "unknown"
    role = b.get("role") or "student"
    text = (b.get("text") or "").strip()[:1000]
    if not text: return jsonify({"ok":False,"error":"empty"}),400
    ts = int(time.time()*1000)
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO chat_messages(room,user_id,role,text,ts) VALUES(?,?,?,?,?)",
                    (room,user_id,role,text,ts))
        conn.commit()
    return jsonify({"ok":True,"ts":ts})

@ai.route("/chat/poll", methods=["GET"])
def chat_poll():
    ensure_schema()
    room = request.args.get("room","*")
    since = int(request.args.get("since","0") or 0)
    with _db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, role, text, ts FROM chat_messages WHERE room=? AND ts>? ORDER BY ts ASC",
                    (room, since))
        rows = [{"user_id":u,"role":r,"text":t,"ts":ts} for (u,r,t,ts) in cur.fetchall()]
    return jsonify({"ok":True,"messages":rows})
