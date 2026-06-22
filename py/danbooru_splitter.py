"""
DanbooruTagSplitter — D站标签拆分节点
输入: artist tag (如 @piromizu)
输出: 角色 / 画师 / 姿势 三类标签字符串
"""

import json, time, threading, requests
from server import PromptServer
from aiohttp import web

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

DANBOORU_BASE = "https://danbooru.donmai.us"
UA = "MooshiePrompt/1.0"
HEADERS = {"User-Agent": UA, "Accept": "application/json"}

_cache = {}
_cache_lock = threading.Lock()

def _cached(key, ttl=300):
    with _cache_lock:
        e = _cache.get(key)
        if e and time.monotonic() - e["ts"] < ttl:
            return e["val"]
    return None

def _cache_set(key, val):
    with _cache_lock:
        _cache[key] = {"val": val, "ts": time.monotonic()}

# ── Tag classification ──────────────────────────
# Danbooru tag categories: 0=general, 1=artist, 3=copyright(series), 4=character, 5=meta
CHARACTER_KEYWORDS = ["girl", "boy", "woman", "man", "male", "female", "loli", "shota",
                      "1girl", "1boy", "2girls", "2boys", "solo"]
POSE_KEYWORDS = ["standing", "sitting", "lying", "walking", "running", "jumping",
                 "looking", "holding", "reaching", "pointing", "kneeling", "leaning",
                 "spread", "arms up", "hands up", "on back", "on stomach", "from behind",
                 "from side", "from above", "from below", "close-up", "full body",
                 "upper body", "profile", "facing viewer", "looking away",
                 "smile", "blush", "open mouth", "closed eyes", "tongue out",
                 "hand on hip", "arms behind back", "crossed arms", "crossed legs"]

def classify_tags(tags_json):
    """Classify Danbooru tags into 角色/画师/姿势."""
    if isinstance(tags_json, str):
        tags = json.loads(tags_json)
    else:
        tags = tags_json

    characters, artists, poses = [], [], []

    for tag_obj in tags:
        name = tag_obj.get("name", "")
        cat = tag_obj.get("category", 0)

        if cat == 1:  # artist
            artists.append(name)
        elif cat == 4:  # character
            characters.append(name)
        elif cat == 0:  # general — check if it matches pose pattern
            name_lower = name.lower().replace("_", " ")
            if any(kw in name_lower for kw in POSE_KEYWORDS) or \
               any(name_lower.startswith(p) for p in ["sitting", "standing", "holding",
                                                       "looking", "arms", "legs", "hands"]):
                poses.append(name)

    return {
        "character": ", ".join(characters),
        "artist": ", ".join(artists),
        "pose": ", ".join(poses),
    }

# ── Danbooru API ────────────────────────────────

def search_posts(artist_tag, limit=20):
    """Search Danbooru posts by artist tag."""
    clean = artist_tag.replace("@", "").strip()
    cache_key = f"search_{clean}_{limit}"
    cached = _cached(cache_key)
    if cached: return cached

    url = f"{DANBOORU_BASE}/posts.json"
    params = {"tags": clean, "limit": limit, "page": 1}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            posts = r.json()
            _cache_set(cache_key, posts)
            return posts
    except Exception as e:
        print(f"[DanbooruSplitter] search error: {e}")
    return []

def get_post_tags(post_id):
    """Get tag details for a specific post."""
    cache_key = f"tags_{post_id}"
    cached = _cached(cache_key)
    if cached: return cached

    url = f"{DANBOORU_BASE}/posts/{post_id}.json"
    try:
        r = requests.get(url, params={"only": "tags"}, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            tags_str = data.get("tag_string", "")
            # Get tag categories — need separate request
            tag_list = []
            for t in tags_str.split():
                tag_list.append({"name": t, "category": 0})
            _cache_set(cache_key, tag_list)
            return tag_list
    except Exception as e:
        print(f"[DanbooruSplitter] tag fetch error: {e}")
    return []

# ── API Routes for JS frontend ──────────────────

async def handle_search(request):
    """Search Danbooru posts and return preview data."""
    artist = request.query.get("artist", "")
    if not artist: return web.json_response({"error": "no artist"}, status=400)
    posts = search_posts(artist, 20)
    results = []
    for p in posts[:20]:
        results.append({
            "id": p["id"],
            "preview_url": p.get("preview_file_url") or p.get("large_file_url", ""),
            "tag_string": p.get("tag_string", ""),
            "rating": p.get("rating", "s"),
            "score": p.get("score", 0),
        })
    return web.json_response(results)

async def handle_classify(request):
    """Classify a post's tags into categories."""
    try:
        body = await request.json()
        post_id = body.get("post_id", 0)
        tags = body.get("tags", [])
        if not tags and post_id:
            tags = get_post_tags(post_id)
        result = classify_tags(tags)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

def register_routes():
    PromptServer.instance.app.router.add_get("/mooshie/search_posts", handle_search)
    PromptServer.instance.app.router.add_post("/mooshie/classify_tags", handle_classify)

# ── ComfyUI Node ─────────────────────────────────

class DanbooruTagSplitter:
    """Search Danbooru by artist tag and split tags into 角色/画师/姿势."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "artist_tag": ("STRING", {
                    "multiline": False,
                    "default": "",
                    "tooltip": "Artist tag from MooshieBrowser (e.g. @piromizu)"
                }),
                "post_id": ("INT", {
                    "default": 0, "min": 0, "max": 99999999,
                    "tooltip": "Danbooru post ID. Set to 0 to auto-pick first result."
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("character_tags", "artist_tags", "pose_tags", "all_tags", "preview_image")
    FUNCTION = "split"
    CATEGORY = "mooshie"
    DESCRIPTION = "Search Danbooru by artist, pick a post, split tags into 角色/画师/姿势."

    def split(self, artist_tag, post_id):
        if not artist_tag.strip():
            return ("", "", "", "", torch.zeros(1, 64, 64, 3))

        posts = search_posts(artist_tag, 20)
        if not posts:
            print(f"[DanbooruSplitter] No posts found for '{artist_tag}'")
            return ("", "", "", "", torch.zeros(1, 64, 64, 3))

        # Pick post: user-specified or first
        post = None
        if post_id > 0:
            post = next((p for p in posts if p["id"] == post_id), None)
        if not post:
            post = posts[0]

        tags = get_post_tags(post["id"])
        classified = classify_tags(tags)

        all_tags = post.get("tag_string", "")

        # Try to load preview image
        preview = torch.zeros(1, 64, 64, 3)
        try:
            import torch, numpy as np
            from PIL import Image
            from io import BytesIO
            preview_url = post.get("preview_file_url", "")
            if preview_url:
                r = requests.get(preview_url, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    img = Image.open(BytesIO(r.content)).convert("RGB")
                    img = img.resize((256, 256), Image.LANCZOS)
                    arr = np.array(img).astype(np.float32) / 255.0
                    preview = torch.from_numpy(arr).unsqueeze(0)
        except Exception as e:
            print(f"[DanbooruSplitter] preview load error: {e}")

        print(f"[DanbooruSplitter] Post #{post['id']}: {len(tags)} tags → "
              f"角色:{len(classified['character'].split(','))} 画师:{len(classified['artist'].split(','))} 姿势:{len(classified['pose'].split(','))}")

        return (
            classified["character"],
            classified["artist"],
            classified["pose"],
            all_tags,
            preview,
        )


NODE_CLASS_MAPPINGS["DanbooruTagSplitter"] = DanbooruTagSplitter
NODE_DISPLAY_NAME_MAPPINGS["DanbooruTagSplitter"] = "Danbooru Tag Splitter (D站标签拆分)"
