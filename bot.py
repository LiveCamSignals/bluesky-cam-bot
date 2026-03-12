import os
import time
import sqlite3
import random
import logging
import requests
from datetime import datetime, timedelta
from atproto import Client

API_URL = "https://chaturbate.com/affiliates/api/onlinerooms/?format=json&wm=T2CSW"

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASS = os.getenv("BLUESKY_PASSWORD")

POST_INTERVAL = 840  # 14 minutes
MAX_VIEWERS_CACHE = 30

DB_FILE = "posted_rooms.db"

NICHES = {
    "bbw": ["bbw"],
    "milf": ["milf"],
    "asian": ["asian"],
    "latina": ["latina"],
    "ebony": ["ebony"],
    "couple": ["couple"]
}

HASHTAGS = [
    "LiveCams",
    "Chaturbate",
    "nsfw",
    "bskynsfw"
]

logging.basicConfig(level=logging.INFO)


# ======================
# DATABASE
# ======================

def init_db():

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS posted (
        username TEXT,
        posted_at DATETIME
    )
    """)

    conn.commit()
    conn.close()


def already_posted(username):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "SELECT posted_at FROM posted WHERE username=?",
        (username,)
    )

    row = c.fetchone()
    conn.close()

    if not row:
        return False

    last_post = datetime.fromisoformat(row[0])

    return datetime.now() - last_post < timedelta(days=30)


def save_post(username):

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        "INSERT INTO posted VALUES (?, ?)",
        (username, datetime.now().isoformat())
    )

    conn.commit()
    conn.close()


# ======================
# FETCH ROOMS
# ======================

def fetch_rooms():

    r = requests.get(API_URL, timeout=15)
    r.raise_for_status()

    return r.json()


# ======================
# FILTER BY NICHE
# ======================

def filter_niche(rooms, niche):

    tags = NICHES[niche]

    results = []

    for r in rooms:

        if r.get("gender") != "f":
            continue

        if r.get("current_show") != "public":
            continue

        room_tags = [t.lower() for t in r.get("tags", [])]

        if not any(t in room_tags for t in tags):
            continue

        if already_posted(r["username"]):
            continue

        results.append(r)

    results.sort(key=lambda x: int(x.get("num_users", 0)), reverse=True)

    return results


# ======================
# BUILD POST
# ======================

def build_text(room):

    subject = room.get("room_subject", "")

    if len(subject) > 80:
        subject = subject[:80] + "..."

    text = f"""
🔥 LIVE NOW ({room['num_users']} watching)

{room['username']} • {room['age']} • {room['country']}

{subject}

👉 Watch free

{' '.join('#'+h for h in HASHTAGS)}
"""

    return text.strip()


# ======================
# POST
# ======================

def post_room(client, room):

    img = requests.get(room["image_url_360x270"]).content

    text = build_text(room)

    client.send_image(
        text=text,
        image=img,
        image_alt=f"{room['username']} live cam"
    )

    save_post(room["username"])

    logging.info(
        f"Posted {room['username']} ({room['num_users']} viewers)"
    )


# ======================
# MAIN LOOP
# ======================

def run_bot():

    client = Client()
    client.login(BLUESKY_HANDLE, BLUESKY_PASS)

    logging.info("Logged into Bluesky")

    niche_cycle = list(NICHES.keys())
    niche_index = 0

    while True:

        try:

            rooms = fetch_rooms()

            niche = niche_cycle[niche_index]

            logging.info(f"Scanning niche: {niche}")

            filtered = filter_niche(rooms, niche)

            if filtered:

                room = random.choice(filtered[:MAX_VIEWERS_CACHE])

                post_room(client, room)

            else:
                logging.info("No rooms available")

            niche_index = (niche_index + 1) % len(niche_cycle)

        except Exception as e:
            logging.warning(e)

        time.sleep(POST_INTERVAL)


# ======================

if __name__ == "__main__":

    init_db()

    run_bot()
