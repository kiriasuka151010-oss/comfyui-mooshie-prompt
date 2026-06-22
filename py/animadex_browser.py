"""
MooshieBrowser — ComfyUI 节点
上半：Mooshieblob 画师浏览  下半：D站作品选择  合并输出标签
"""
import json, asyncio, requests, random, os, re, threading, time as _time
from server import PromptServer
from aiohttp import web

from .mooshie_data import search as mooshie_search, get_facets as mooshie_facets

# D站 UA 必须和原版一致（Danbooru API 要求描述性 UA）
DANBOORU_UA = "DanbooruAnimaPrompt/1.0 (Anime tag classifier)"
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": DANBOORU_UA, "Accept": "application/json"})

# D站帖子缓存
_post_cache = {}
_cache_lock = asyncio.Lock()


# ── Mooshie 搜索（不变） ──

def _search(mode, query, limit=36, filters=None, page=1, sort="count"):
    results, total = mooshie_search(query, limit=limit, page=page, sort=sort)
    return results, total

def _search_facets(mode):
    return mooshie_facets()

def _batch_search(mode, queries, limit=36):
    seen = set()
    merged = []
    for q in queries:
        q = q.strip()
        if not q:
            continue
        res, _total = _search(mode, q, limit)
        for r in res:
            s = r.get("slug", "")
            if s and s not in seen:
                seen.add(s)
                merged.append(r)
    return merged


# ── D站 API ──

def _danbooru_search(tag, page=1, limit=24):
    """搜索 D站帖子 — 与原版 search_posts 一致的 UA"""
    tags = tag.strip().lstrip("@")
    params = {"tags": tags, "page": page, "limit": min(limit, 100)}
    try:
        r = _SESSION.get("https://danbooru.donmai.us/posts.json", params=params, timeout=10)
        if r.status_code != 200:
            return [], 0
        return r.json(), len(r.json())
    except Exception:
        return [], 0


def _get_post_from_danbooru(post_id):
    """获取单帖详情（带缓存）"""
    if post_id in _post_cache:
        return _post_cache[post_id]
    try:
        r = _SESSION.get(f"https://danbooru.donmai.us/posts/{post_id}.json", timeout=10)
        if r.status_code != 200:
            return None
        post = r.json()
        _post_cache[post_id] = post
        return post
    except Exception:
        return None


# ── 节点 ──

class MooshieBrowser:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "_tag": ("STRING", {"default": "", "multiline": False}),
                "selection_data": ("STRING", {"default": "{}", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("artist_tag", "artist_tags", "char_tags", "general_tags",
                    "series_tags", "meta_tags")
    FUNCTION = "browse"
    CATEGORY = "mooshie"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def browse(self, _tag="", selection_data="{}"):
        artist_tag = (_tag or "").strip()
        try:
            sel = json.loads(selection_data)
        except json.JSONDecodeError:
            sel = {}

        post_id = sel.get("post_id")
        if post_id:
            post = _get_post_from_danbooru(post_id)
            if post:
                return (
                    artist_tag,
                    post.get("tag_string_artist", ""),
                    post.get("tag_string_character", ""),
                    post.get("tag_string_general", ""),
                    post.get("tag_string_copyright", ""),
                    post.get("tag_string_meta", ""),
                )

        return (artist_tag, "", "", "", "", "")


# ── API 路由 ──

def register_routes():
    # 图片代理
    @PromptServer.instance.routes.get("/mooshie/image")
    async def mooshie_image(request):
        url = request.query.get("url")
        if not url:
            return web.json_response({"error": "missing url"}, status=400)
        try:
            resp = await asyncio.to_thread(_SESSION.get, url, timeout=15)
            if resp.status_code == 200:
                ct = resp.headers.get("Content-Type", "image/jpeg")
                return web.Response(body=resp.content, content_type=ct,
                                    headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass
        return web.json_response({"error": "proxy fail"}, status=502)

    # Mooshie 画师搜索
    @PromptServer.instance.routes.post("/mooshie/search")
    async def mooshie_search_route(request):
        try:
            data = await request.json()
            mode = data.get("mode", "artists")
            raw = data.get("query", "").strip()
            filters = data.get("filters", {})
            page = int(data.get("page", 1))
            sort = data.get("sort", "count")
            queries = [q.strip() for q in raw.replace(",", " ").split() if q.strip()]
            if not queries:
                if sort == "random":
                    _tmp, total = _search(mode, "", 1, filters, 1, "count")
                    if total > 0:
                        page = random.randint(1, max(1, total // 36))
                results, total = _search(mode, "", 36, filters, page, sort)
                return web.json_response({"success": True, "results": results, "total": total})
            return web.json_response({"success": True, "results": _batch_search(mode, queries, 36)})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    @PromptServer.instance.routes.post("/mooshie/facets")
    async def mooshie_facets_route(request):
        try:
            data = await request.json()
            return web.json_response({"success": True, "facets": _search_facets(data.get("mode", "artists"))})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # D站帖子搜索
    @PromptServer.instance.routes.post("/mooshie/danbooru/search")
    async def danbooru_search_route(request):
        try:
            data = await request.json()
            tag = data.get("tag", "")
            page = int(data.get("page", 1))
            posts, _count = _danbooru_search(tag, page)
            # 简化返回，只返回前端需要的字段
            simplified = [{
                "id": p["id"],
                "preview_url": p.get("preview_file_url") or p.get("large_file_url", ""),
                "large_url": p.get("large_file_url") or p.get("file_url", ""),
                "file_url": p.get("file_url", ""),
                "tag_string": p.get("tag_string", ""),
                "tag_string_artist": p.get("tag_string_artist", ""),
                "tag_string_character": p.get("tag_string_character", ""),
                "tag_string_general": p.get("tag_string_general", ""),
                "tag_string_copyright": p.get("tag_string_copyright", ""),
                "tag_string_meta": p.get("tag_string_meta", ""),
                "rating": p.get("rating", "s"),
                "score": p.get("score", 0),
                "image_width": p.get("image_width", 0),
                "image_height": p.get("image_height", 0),
                "is_video": p.get("file_ext", "") in ("mp4", "webm"),
            } for p in posts if p.get("preview_file_url")]
            return web.json_response({"success": True, "posts": simplified})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # D站帖子详情（返回分类标签 + 全量信息）
    @PromptServer.instance.routes.get("/mooshie/post/{post_id}")
    async def mooshie_post_route(request):
        try:
            post_id = int(request.match_info.get("post_id", 0))
            if not post_id:
                return web.json_response({"error": "missing id"}, status=400)
            post = _get_post_from_danbooru(post_id)
            if not post:
                return web.json_response({"error": "not found"}, status=404)
            # 解析标签并按分类分组
            tag_string = post.get("tag_string", "")
            tags = [t.strip() for t in tag_string.split() if t.strip()]
            classified = _classify_tags(tags)
            return web.json_response({
                "success": True,
                "post": {
                    "id": post["id"],
                    "preview_url": post.get("preview_file_url", ""),
                    "large_url": post.get("large_file_url") or post.get("file_url", ""),
                    "file_url": post.get("file_url", ""),
                    "rating": post.get("rating", "s"),
                    "score": post.get("score", 0),
                    "image_width": post.get("image_width", 0),
                    "image_height": post.get("image_height", 0),
                    "tag_string_artist": post.get("tag_string_artist", ""),
                    "tag_string_character": post.get("tag_string_character", ""),
                    "tag_string_general": post.get("tag_string_general", ""),
                    "tag_string_copyright": post.get("tag_string_copyright", ""),
                    "tag_string_meta": post.get("tag_string_meta", ""),
                },
                "classified": classified,
                "total_tags": len(tags),
            })
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # ── 收藏系统 ──
    _fav_lock = threading.Lock()
    _FAV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mooshie_favorites.json")

    def _load_favs():
        try:
            if os.path.exists(_FAV_FILE):
                with open(_FAV_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_favs(favs):
        os.makedirs(os.path.dirname(_FAV_FILE), exist_ok=True)
        with open(_FAV_FILE, "w", encoding="utf-8") as f:
            json.dump(favs, f, ensure_ascii=False, indent=2)

    @PromptServer.instance.routes.get("/mooshie/favorites")
    async def fav_list(request):
        return web.json_response({"success": True, "favorites": _load_favs()})

    @PromptServer.instance.routes.post("/mooshie/favorites/add")
    async def fav_add(request):
        try:
            data = await request.json()
            post = data.get("post")
            if not post or not post.get("id"):
                return web.json_response({"success": False, "error": "missing post"}, status=400)
            with _fav_lock:
                favs = _load_favs()
                # 去重
                favs = [f for f in favs if f.get("id") != post["id"]]
                post["added_at"] = _time.time()
                favs.insert(0, post)
                _save_favs(favs)
            return web.json_response({"success": True, "count": len(favs)})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    @PromptServer.instance.routes.post("/mooshie/favorites/remove")
    async def fav_remove(request):
        try:
            data = await request.json()
            post_id = data.get("id")
            if not post_id:
                return web.json_response({"success": False, "error": "missing id"}, status=400)
            with _fav_lock:
                favs = _load_favs()
                favs = [f for f in favs if f.get("id") != post_id]
                _save_favs(favs)
            return web.json_response({"success": True, "count": len(favs)})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)


# ── 简易标签分类 ──

_COUNT_PATTERN = re.compile(r'^\d+(girl|boy|other|people)s?$', re.IGNORECASE)
_META_TAGS = {"masterpiece", "best_quality", "highres", "absurdres", "lowres",
              "worst_quality", "bad_quality", "normal_quality", "watermark",
              "signature", "artist_name", "commission", "translated"}
_YEAR_PATTERN = re.compile(r'^\d{4}$')

def _classify_tags(tags):
    groups = {"quality_meta": [], "count": [], "character": [], "series": [],
              "artist": [], "general": [], "all": list(tags)}
    for t in tags:
        lt = t.lower()
        if lt.startswith("rating:") or lt in _META_TAGS or _YEAR_PATTERN.match(lt):
            groups["quality_meta"].append(t)
        elif _COUNT_PATTERN.match(lt):
            groups["count"].append(t)
        else:
            groups["general"].append(t)
    return groups


NODE_CLASS_MAPPINGS = {"MooshieBrowser": MooshieBrowser}
NODE_DISPLAY_NAME_MAPPINGS = {"MooshieBrowser": "Mooshie 艺术家浏览器 (Mooshie Browser)"}
