#!/usr/bin/env python3
"""Writing desk for the blog.

Run `python3 write.py` and a page opens in your browser where you can write
posts, add photos, and publish them to the website. It only runs on this
computer; nothing is reachable from the internet.
"""
import base64
import json
import os
import re
import subprocess
import sys
import unicodedata
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS = ROOT / "posts"
IMAGES = ROOT / "images"
INDEX = POSTS / "index.json"
PORT = int(os.environ.get("PORT", 4000))
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "post"


def unique(taken, base):
    name, n = base, 2
    while taken(name):
        name, n = f"{base}-{n}", n + 1
    return name


def excerpt(body):
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s*[#>]+\s*", "", text, flags=re.M)
    text = re.sub(r"[*_`]", "", text)
    text = " ".join(text.split())
    return text if len(text) <= 180 else text[:180].rsplit(" ", 1)[0] + "…"


def read_index():
    return json.loads(INDEX.read_text()) if INDEX.exists() else []


def write_index(posts):
    posts.sort(key=lambda p: p["date"], reverse=True)
    INDEX.write_text(json.dumps(posts, indent=2, ensure_ascii=False) + "\n")


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def save_post(data):
    title = data.get("title", "").strip()
    date = data.get("date", "")
    if not title:
        raise ValueError("Give the post a title first.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("Pick a date for the post.")
    posts = read_index()
    slug = data.get("slug") or unique(lambda s: any(p["slug"] == s for p in posts), slugify(title))
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError("Invalid post name.")
    body = data.get("body", "").strip() + "\n"
    POSTS.mkdir(exist_ok=True)
    (POSTS / f"{slug}.md").write_text(body)
    entry = {
        "slug": slug,
        "title": title,
        "date": date,
        "location": data.get("location", "").strip(),
        "cover": data.get("cover", ""),
        "excerpt": excerpt(body),
    }
    write_index([entry] + [p for p in posts if p["slug"] != slug])
    return {"slug": slug}


def delete_post(data):
    slug = data.get("slug", "")
    if not re.fullmatch(r"[a-z0-9-]+", slug):
        raise ValueError("Invalid post name.")
    (POSTS / f"{slug}.md").unlink(missing_ok=True)
    write_index([p for p in read_index() if p["slug"] != slug])
    return {}


def upload_photo(data):
    folder = data.get("dir", "")
    if not re.fullmatch(r"[a-z0-9-]{1,80}", folder):
        raise ValueError("Invalid photo folder.")
    m = re.fullmatch(r"data:(image/[a-z]+);base64,(.+)", data.get("data", ""), flags=re.S)
    if not m or m.group(1) not in IMAGE_TYPES:
        raise ValueError("That file is not a photo this blog can use.")
    ext = IMAGE_TYPES[m.group(1)]
    target = IMAGES / folder
    target.mkdir(parents=True, exist_ok=True)
    stem = unique(lambda s: (target / (s + ext)).exists(), slugify(Path(data.get("name", "photo")).stem))
    (target / (stem + ext)).write_bytes(base64.b64decode(m.group(2)))
    return {"path": f"images/{folder}/{stem}{ext}"}


def publish(_data):
    git("add", "-A")
    if git("diff", "--cached", "--quiet")[0] != 0:
        code, out = git("commit", "-m", "Update blog")
        if code != 0:
            raise RuntimeError(out)
    code, out = git("push")
    if code != 0:
        raise RuntimeError(out)
    return {"log": out}


def status(_data=None):
    changed = git("status", "--porcelain")[1]
    ahead = git("rev-list", "--count", "@{u}..HEAD")[1]
    return {"unpublished": bool(changed) or ahead not in ("", "0")}


ACTIONS = {"/api/save": save_post, "/api/delete": delete_post, "/api/upload": upload_photo, "/api/publish": publish}


class Handler(SimpleHTTPRequestHandler):
    def reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/status":
            return self.reply(200, status())
        super().do_GET()

    def do_POST(self):
        # Only this computer's own writing page may change the blog.
        local = (f"localhost:{PORT}", f"127.0.0.1:{PORT}")
        origin = self.headers.get("Origin")
        if self.headers.get("Host") not in local or (origin and origin.split("//")[-1] not in local):
            return self.reply(403, {"error": "Not allowed."})
        action = ACTIONS.get(self.path)
        if not action:
            return self.reply(404, {"error": "Unknown action."})
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            self.reply(200, action(data))
        except (ValueError, RuntimeError) as e:
            self.reply(400, {"error": str(e)})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(ROOT)))
    url = f"http://localhost:{PORT}/admin/"
    print(f"Writing desk: {url}\nBlog preview: http://localhost:{PORT}/\nPress Ctrl+C to stop.")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
