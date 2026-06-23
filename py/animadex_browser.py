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

def _danbooru_search(tag, page=1, limit=24, rating=None):
    """搜索 D站帖子 — 与原版 search_posts 一致的 UA"""
    tags = tag.strip().lstrip("@")
    if rating:
        tags += f" rating:{rating}"
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

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("artist_tag", "tag_data")
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
                tag_data = json.dumps({
                    "artist": post.get("tag_string_artist", ""),
                    "character": post.get("tag_string_character", ""),
                    "series": post.get("tag_string_copyright", ""),
                    "general": post.get("tag_string_general", ""),
                    "meta": post.get("tag_string_meta", ""),
                })
                return (
                    artist_tag,
                    tag_data,
                )

        return (artist_tag, "{}")


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
            rating = data.get("rating") or None
            posts, _count = _danbooru_search(tag, page, rating=rating)
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

    # ── 模糊标签搜索 ──
    _cn_tags = None  # {english_tag: chinese_name}

    def _load_cn_tags():
        nonlocal _cn_tags
        if _cn_tags is not None:
            return
        _cn_tags = {}
        my_dir = os.path.dirname(os.path.abspath(__file__))
        custom_nodes = os.path.dirname(os.path.dirname(my_dir))
        zh_dir = os.path.join(custom_nodes, "ComfyUI-Danbooru-Anima-Prompt", "py", "zh_cn")

        # 0. 内置角色映射（无文件依赖）
        _cn_tags.update({
            "hu_tao_(genshin_impact)": "胡桃", "ganyu_(genshin_impact)": "甘雨",
            "keqing_(genshin_impact)": "刻晴", "raiden_shogun_(genshin_impact)": "雷电将军",
            "nahida_(genshin_impact)": "纳西妲", "furina_(genshin_impact)": "芙宁娜",
            "rem_(re:zero)": "蕾姆", "ram_(re:zero)": "拉姆", "emilia_(re:zero)": "爱蜜莉雅",
            "hatsune_miku": "初音未来", "blue_archive": "碧蓝档案",
            "amiya_(arknights)": "阿米娅", "exusiai_(arknights)": "能天使",
            "skadi_(arknights)": "斯卡蒂", "surtr_(arknights)": "史尔特尔",
        })

        # 1. 标签中英对照
        jp = os.path.join(zh_dir, "all_tags_cn.json")
        if os.path.exists(jp):
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    _cn_tags.update(json.load(f))
                print(f"[Mooshie] 标签索引: {len(_cn_tags)} 条")
            except Exception:
                pass

        # 2. 角色名 CSV (中→英)
        import csv as csv_import
        cp = os.path.join(zh_dir, "wai_characters.csv")
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    for row in csv_import.reader(f):
                        if len(row) >= 2 and row[0].strip() and row[1].strip():
                            _cn_tags.setdefault(row[1].strip(), row[0].strip())
            except Exception as e:
                print(f"[Mooshie] 角色索引加载失败: {e}")

        # 3. 海量标签 CSV (50k条, GBK编码)
        enhanced_paths = [
            os.path.join(custom_nodes, "ComfyUI-Danbooru-Anima-Prompt", "tags_enhanced.csv"),
            os.path.join(os.path.dirname(custom_nodes), "tags_enhanced.csv"),
        ]
        for cpath in enhanced_paths:
            if not os.path.exists(cpath):
                continue
            for enc in ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]:
                try:
                    with open(cpath, "r", encoding=enc, newline="") as f:
                        # 先跳过 header
                        next(f)
                        for row in csv_import.reader(f):
                            if len(row) >= 2 and row[0].strip() and row[1].strip():
                                en_tag = row[0].strip()
                                cn_raw = row[1].strip()
                                # cn_name 可能是逗号分隔的多个翻译，取第一个
                                cn_first = cn_raw.split(",")[0].strip()
                                if cn_first and en_tag not in _cn_tags:
                                    _cn_tags[en_tag] = cn_first
                    break  # 成功就退出编码尝试
                except (UnicodeDecodeError, StopIteration):
                    continue
            break  # 成功就退出路径尝试
        print(f"[Mooshie] 索引就绪: {len(_cn_tags)} 条")

    @PromptServer.instance.routes.post("/mooshie/fuzzy_tags")
    async def fuzzy_tags_route(request):
        try:
            data = await request.json()
            query = data.get("query", "").strip()
            if not query or len(query) < 1:
                return web.json_response({"success": True, "tags": []})
            _load_cn_tags()
            q = query.lower()
            results = []
            # 查找中文匹配
            for en_tag, cn_name in _cn_tags.items():
                if q in cn_name.lower() or q in en_tag.lower():
                    results.append({"tag": en_tag, "cn": cn_name})
                if len(results) >= 15:
                    break
            return web.json_response({"success": True, "tags": results})
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
