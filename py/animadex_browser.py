"""
MooshieBrowser — ComfyUI 节点
浏览 Mooshieblob 画师画廊，预览图片，输出 @artist_tag
数据源: cdn.mooshieblob.com search.json (42k+ 艺术家)
"""
import json, asyncio, requests, random
from server import PromptServer
from aiohttp import web

from .mooshie_data import search as mooshie_search, get_facets as mooshie_facets

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "ComfyUI-Mooshie/1.0", "Accept": "application/json"})


def _search(mode, query, limit=36, filters=None, page=1, sort="count"):
    """搜索 Mooshieblob 艺术家"""
    results, total = mooshie_search(query, limit=limit, page=page, sort=sort)

    # sort=random 时 mooshie_data 已做 shuffle，但 page 需要重新计算
    # 这里保持简单：直接返回分页结果
    return results, total


def _search_facets(mode):
    return mooshie_facets()


def _batch_search(mode, queries, limit=36):
    """搜索多个 query 合并去重"""
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


class MooshieBrowser:
    """Mooshie 艺术家浏览器"""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"_tag": ("STRING", {"default": "", "multiline": False})}}

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("tag",)
    FUNCTION = "run"
    CATEGORY = "mooshie"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("NaN")

    def run(self, _tag=""):
        return (_tag or "",)


# ── API 路由 ──

def register_routes():
    @PromptServer.instance.routes.get("/mooshie/image")
    async def mooshie_image(request):
        """图片代理：代理 CDN 图片"""
        url = request.query.get("url")
        if not url:
            return web.json_response({"error": "missing url"}, status=400)
        try:
            resp = await asyncio.to_thread(_SESSION.get, url, timeout=15)
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "image/avif")
                return web.Response(body=resp.content, content_type=content_type,
                                    headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            pass
        return web.json_response({"error": "proxy fail"}, status=502)

    @PromptServer.instance.routes.post("/mooshie/search")
    async def animadex_search(request):
        try:
            data = await request.json()
            mode = data.get("mode", "characters")
            raw = data.get("query", "").strip()
            filters = data.get("filters", {})
            page = int(data.get("page", 1))
            sort = data.get("sort", "count")
            queries = [q.strip() for q in raw.replace(",", " ").split() if q.strip()]
            if not queries:
                # sort=random → 随机翻到任意页
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
    async def animadex_facets(request):
        try:
            data = await request.json()
            mode = data.get("mode", "characters")
            return web.json_response({"success": True, "facets": _search_facets(mode)})
        except Exception as e:
            return web.json_response({"success": False, "error": str(e)}, status=500)


NODE_CLASS_MAPPINGS = {"MooshieBrowser": MooshieBrowser}
NODE_DISPLAY_NAME_MAPPINGS = {"MooshieBrowser": "Mooshie 艺术家浏览器 (Mooshie Browser)"}
