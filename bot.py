import os
import logging
import requests
from atproto import Client, models

API_URL = "https://chaturbate.com/affiliates/api/onlinerooms/?format=json&wm=T2CSW"

BLUESKY_HANDLE = os.getenv("BLUESKY_HANDLE")
BLUESKY_PASSWORD = os.getenv("BLUESKY_PASSWORD")

logging.basicConfig(level=logging.INFO)

session = requests.Session()


# -----------------------------
# FACET BUILDER
# -----------------------------

def build_facets(text, link, hashtags):

    facets = []

    def get_bytes(sub):
        start = text.find(sub)
        if start == -1:
            return None

        byte_start = len(text[:start].encode("utf-8"))
        byte_end = byte_start + len(sub.encode("utf-8"))

        return models.AppBskyRichtextFacet.ByteSlice(
            byteStart=byte_start,
            byteEnd=byte_end
        )

    # clickable link
    link_text = "Watch free"
    index = get_bytes(link_text)

    if index:
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=index,
                features=[models.AppBskyRichtextFacet.Link(uri=link)]
            )
        )

    # clickable hashtags
    for tag in hashtags:

        tag_text = f"#{tag}"

        index = get_bytes(tag_text)

        if index:
            facets.append(
                models.AppBskyRichtextFacet.Main(
                    index=index,
                    features=[models.AppBskyRichtextFacet.Tag(tag=tag)]
                )
            )

    return facets


# -----------------------------
# FETCH ROOMS
# -----------------------------

def fetch_rooms():

    logging.info("Fetching rooms from API")

    r = session.get(API_URL, timeout=20)
    r.raise_for_status()

    data = r.json()

    logging.info(f"{len(data)} rooms received")

    return data


# -----------------------------
# SELECT ROOM
# -----------------------------

def select_room(rooms):

    # basic safe filter
    candidates = [
        r for r in rooms
        if r.get("gender") == "f"
        and r.get("current_show") == "public"
    ]

    if not candidates:
        logging.info("No filtered rooms, using full list")
        candidates = rooms

    # sort by viewers
    candidates.sort(
        key=lambda x: int(x.get("num_users", 0)),
        reverse=True
    )

    room = candidates[0]

    logging.info(
        f"Selected {room['username']} with {room['num_users']} viewers"
    )

    return room


# -----------------------------
# BUILD POST
# -----------------------------

def build_post(room):

    username = room["username"]
    viewers = room.get("num_users", 0)
    age = room.get("age", "?")
    country = room.get("country") or "??"
    subject = room.get("room_subject", "")

    if len(subject) > 80:
        subject = subject[:80] + "..."

    # performer tags
    tags = room.get("tags", [])[:5]

    hashtags = [t.replace(" ", "") for t in tags]

    hashtags.extend([
        "LiveCams",
        "Chaturbate",
        "nsfw"
    ])

    hashtag_text = " ".join(f"#{h}" for h in hashtags)

    text = (
        f"🔥 {username} LIVE NOW ({viewers} watching)\n\n"
        f"{username} • {age} • {country}\n"
        f"{subject}\n\n"
        f"👉 Watch free\n\n"
        f"{hashtag_text}"
    )

    return text, hashtags


# -----------------------------
# POST
# -----------------------------

def post_room(client, room):

    image_url = room.get("image_url")

    logging.info("Downloading thumbnail")

    img = session.get(image_url, timeout=15).content

    text, hashtags = build_post(room)

    link = room["chat_room_url_revshare"]

    facets = build_facets(text, link, hashtags)

    logging.info("Posting to Bluesky")

    client.send_image(
        text=text,
        image=img,
        image_alt=f"{room['username']} live cam",
        facets=facets
    )

    logging.info("Post successful")


# -----------------------------
# MAIN
# -----------------------------

def main():

    logging.info("Bot starting")

    client = Client()

    client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)

    logging.info("Logged into Bluesky")

    rooms = fetch_rooms()

    room = select_room(rooms)

    post_room(client, room)

    logging.info("Bot finished")


# -----------------------------

if __name__ == "__main__":
    main()
