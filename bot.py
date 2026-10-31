
import os
import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ==============================
# FC MOBILE GLITCH ALERT BOT
# ==============================

DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

SEEN_FILE = "seen.json"

SEARCHES = [
    "FC Mobile glitch",
    "FC Mobile coin glitch",
    "FC Mobile pack glitch",
    "FC Mobile free gems glitch",
    "FC Mobile player glitch"
]

def get_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FCMobileGlitchBot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read())

def get_reddit():
    results = []

    for term in SEARCHES:
        url = "https://www.reddit.com/search.rss?" + urllib.parse.urlencode({
            "q": term,
            "sort": "new",
            "t": "week"
        })

        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "FCMobileGlitchBot/1.0"}
            )

            with urllib.request.urlopen(request, timeout=25) as response:
                root = ET.fromstring(response.read())

            ns = {"a": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("a:entry", ns):
                title = entry.findtext("a:title", "", ns)
                link = entry.find("a:link", ns)
                post_url = link.attrib.get("href", "") if link is not None else ""
                post_id = entry.findtext("a:id", post_url, ns)

                if title and post_url:
                    results.append({
                        "id": "reddit:" + post_id,
                        "title": title,
                        "url": post_url,
                        "source": "Reddit"
                    })

        except Exception as error:
            print("Reddit error:", error)

    return results

def get_youtube():
    results = []

    if not YOUTUBE_API_KEY:
        print("YouTube skipped: API key not configured.")
        return results

    for term in SEARCHES:
        params = urllib.parse.urlencode({
            "part": "snippet",
            "type": "video",
            "order": "date",
            "publishedAfter": (
                datetime.now(timezone.utc) - timedelta(days=7)
            ).isoformat().replace("+00:00", "Z"),
            "maxResults": 10,
            "q": term,
            "key": YOUTUBE_API_KEY
        })

        url = "https://www.googleapis.com/youtube/v3/search?" + params

        try:
            data = get_json(url)

            for item in data.get("items", []):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]

                results.append({
                    "id": "youtube:" + video_id,
                    "title": snippet["title"],
                    "url": "https://www.youtube.com/watch?v=" + video_id,
                    "source": "YouTube",
                    "description": snippet.get("description", "")
                })

        except Exception as error:
            print("YouTube error:", error)

    return results

def assess_claim(title, description=""):
    text = (title + " " + description).lower()

    categories = {
        "Coins": ["coin", "coins", "money"],
        "Packs": ["pack", "packs", "player pack"],
        "Gems": ["gem", "gems"],
        "Players": ["player", "ovr", "rank"],
        "Gameplay": ["gameplay", "match", "skill", "training"]
    }

    category = "General"
    for name, words in categories.items():
        if any(word in text for word in words):
            category = name
            break

    suspicious_words = [
        "mod apk", "hack tool", "free fc points generator",
        "password required", "download this file",
        "enter your login", "account generator"
    ]

    suspicious = any(word in text for word in suspicious_words)

    evidence_words = [
        "proof", "tested", "works", "working",
        "update", "tutorial", "gameplay"
    ]

    evidence_signals = sum(word in text for word in evidence_words)

    if suspicious:
        status = "LIKELY FAKE / UNSAFE"
        explanation = "Suspicious wording detected. Do not download files or share account details."
    else:
        status = "UNVERIFIED"
        explanation = "A report was found, but the glitch has not been tested in-game."

    return category, status, explanation, evidence_signals

def send_alert(item):
    category, status, explanation, signals = assess_claim(
        item["title"],
        item.get("description", "")
    )

    role_id = os.environ.get("GLITCH_ROLE_ID", "")
    mention = f"<@&{role_id}> " if role_id else ""

    message = (
        f"{mention}⚡ **FC MOBILE GLITCH REPORT**\n\n"
        f"**Claim:** {item['title'][:250]}\n"
        f"**Category:** {category}\n"
        f"**Source:** {item['source']}\n"
        f"**Status:** {status}\n"
        f"**Evidence signals:** {signals} (not proof)\n\n"
        f"**Assessment:** {explanation}\n"
        f"**Original link:** {item['url']}\n\n"
        "⚠️ Never share your FC Mobile password or download suspicious files."
    )

    payload = json.dumps({
        "content": message,
        "allowed_mentions": {
            "parse": [],
            "roles": [role_id] if role_id else []
        }
    }).encode()

    request = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=25):
        print("Alert sent:", item["title"])

def main():
    try:
        with open(SEEN_FILE, "r") as file:
            seen = set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        seen = set()

    items = get_reddit() + get_youtube()
    new_seen = set(seen)

    for item in items:
        if item["id"] in seen:
            continue

        try:
            send_alert(item)
            new_seen.add(item["id"])
        except Exception as error:
            print("Alert failed:", error)

    with open(SEEN_FILE, "w") as file:
        json.dump(sorted(new_seen), file)

    print("Finished. Sources checked:", len(items))

if __name__ == "__main__":
    main()
