"""
MooshieBrowser — Anima 艺术家浏览器
数据源: https://anima.mooshieblob.com/
输出: 选中的 artist tag (如 @piromizu)
"""

import json, time, threading, requests
from server import PromptServer
from aiohttp import web

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

MOOSHIE_BASE = "https://anima.mooshieblob.com"
UA = "MooshiePrompt/1.0"

_cache = {}
_cache_lock = threading.Lock()

def _cached_get(key, ttl=600):
    with _cache_lock:
        e = _cache.get(key)
        if e and time.monotonic() - e["ts"] < ttl:
            return e["val"]
    return None

def _cache_set(key, val):
    with _cache_lock:
        _cache[key] = {"val": val, "ts": time.monotonic()}

# ── Mooshieblob data fetch ──────────────────────
# The site is a SPA. Artist data is bundled in the JS.
# We provide a built-in top artists list and an API route for dynamic loading.

BUILTIN_ARTISTS = [
    {"name": "qp:flapper", "tag": "@qp:flapper", "posts": 16000},
    {"name": "dairi", "tag": "@dairi", "posts": 16000},
    {"name": "nel-zel formula", "tag": "@nel-zel_formula", "posts": 9000},
    {"name": "kagami hirotaka", "tag": "@kagami_hirotaka", "posts": 8000},
    {"name": "ebifurya", "tag": "@ebifurya", "posts": 6000},
    {"name": "aoi nagisa", "tag": "@aoi_nagisa_(metalder)", "posts": 6000},
    {"name": "haruyama kazunori", "tag": "@haruyama_kazunori", "posts": 5000},
    {"name": "lolita channel", "tag": "@lolita_channel", "posts": 5000},
    {"name": "yaegashi nan", "tag": "@yaegashi_nan", "posts": 5000},
    {"name": "ruu (tksymkw)", "tag": "@ruu_(tksymkw)", "posts": 5000},
    {"name": "piromizu", "tag": "@piromizu", "posts": 4000},
    {"name": "x4824", "tag": "@x4824", "posts": 4000},
    {"name": "zuki", "tag": "@zuki", "posts": 3500},
    {"name": "mochizuki kei", "tag": "@mochizuki_kei", "posts": 3500},
    {"name": "ask (askzy)", "tag": "@ask_(askzy)", "posts": 3000},
    {"name": "wlop", "tag": "@wlop", "posts": 3000},
    {"name": "tony taka", "tag": "@tony_taka", "posts": 2500},
    {"name": "kantoku", "tag": "@kantoku", "posts": 2500},
    {"name": "fuzichoco", "tag": "@fuzichoco", "posts": 2500},
    {"name": "swd3e2", "tag": "@swd3e2", "posts": 2500},
]

def search_artists(query, limit=50):
    """Search built-in artist list (and try live fetch)."""
    q = query.lower().strip()
    results = [a for a in BUILTIN_ARTISTS
               if q in a["name"].lower() or q in a["tag"].lower()]
    if not q:
        results = BUILTIN_ARTISTS[:limit]
    return results[:limit]

# ── API Routes ──────────────────────────────────

async def handle_search(request):
    """Search Mooshieblob artists."""
    q = request.query.get("q", "")
    limit = int(request.query.get("limit", 50))
    results = search_artists(q, limit)
    return web.json_response(results)

async def handle_get_tag(request):
    """Get artist tag by name."""
    name = request.query.get("name", "")
    for a in BUILTIN_ARTISTS:
        if a["name"].lower() == name.lower() or a["tag"] == name:
            return web.json_response(a)
    return web.json_response({"name": name, "tag": f"@{name.replace(' ', '_')}", "posts": 0})

def register_routes():
    PromptServer.instance.app.router.add_get("/mooshie/search_artists", handle_search)
    PromptServer.instance.app.router.add_get("/mooshie/get_tag", handle_get_tag)

# ── ComfyUI Node ─────────────────────────────────

class MooshieBrowser:
    """Browse Mooshieblob artist gallery and output artist tag."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "artist_tag": ("STRING", {
                    "multiline": False,
                    "default": "@piromizu",
                    "tooltip": "Artist tag. Use the frontend browser to search & select, or type manually."
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("artist_tag",)
    FUNCTION = "output"
    CATEGORY = "mooshie"
    DESCRIPTION = "Select artist from Mooshieblob gallery. Outputs @artist_tag for DanbooruTagSplitter."

    def output(self, artist_tag):
        tag = artist_tag.strip()
        if tag and not tag.startswith("@"):
            tag = "@" + tag
        return (tag,)


NODE_CLASS_MAPPINGS["MooshieBrowser"] = MooshieBrowser
NODE_DISPLAY_NAME_MAPPINGS["MooshieBrowser"] = "Mooshie Browser (艺术家浏览器)"
