"""
MooshieBrowser — ComfyUI 节点
上半：Mooshieblob 画师浏览  下半：D站作品选择  合并输出标签
"""
import json, asyncio, requests, random
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
                "tag_string_artist": p.get("tag_string_artist", ""),
                "tag_string_character": p.get("tag_string_character", ""),
                "tag_string_general": p.get("tag_string_general", ""),
                "tag_string_copyright": p.get("tag_string_copyright", ""),
                "tag_string_meta": p.get("tag_string_meta", ""),
                "rating": p.get("rating", "s"),
                "score": p.get("score", 0),
                "image_width": p.get("image_width", 0),
                "image_height": p.get("image_height", 0),
            } for p in posts if p.get("preview_file_url")]
            return web.json_response({"success": True, "posts": simplified})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)

    # D站帖子详情
    @PromptServer.instance.routes.get("/mooshie/danbooru/post")
    async def danbooru_post_route(request):
        try:
            post_id = int(request.query.get("id", 0))
            if not post_id:
                return web.json_response({"error": "missing id"}, status=400)
            post = _get_post_from_danbooru(post_id)
            if not post:
                return web.json_response({"error": "not found"}, status=404)
            return web.json_response({
                "success": True,
                "post": {
                    "id": post["id"],
                    "tag_string_artist": post.get("tag_string_artist", ""),
                    "tag_string_character": post.get("tag_string_character", ""),
                    "tag_string_general": post.get("tag_string_general", ""),
                    "tag_string_copyright": post.get("tag_string_copyright", ""),
                    "tag_string_meta": post.get("tag_string_meta", ""),
                }
            })
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)


NODE_CLASS_MAPPINGS = {"MooshieBrowser": MooshieBrowser}
NODE_DISPLAY_NAME_MAPPINGS = {"MooshieBrowser": "Mooshie 艺术家浏览器 (Mooshie Browser)"}
