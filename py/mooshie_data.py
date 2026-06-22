"""
Mooshie 数据加载器 — 从 CDN 下载 search.json，缓存在本地，内存搜索
"""
import json, os, time, requests

CDN_BASE = "https://cdn.mooshieblob.com"
RELEASE = "20260425_anima_all_artists"
SEARCH_URL = f"{CDN_BASE}/{RELEASE}/indices/search.json"
IMAGE_BASE = f"{CDN_BASE}/{RELEASE}/images"

# 本地缓存路径
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "search.json")
CACHE_TTL = 86400 * 7  # 一周更新一次

# 内存缓存
_data = None
_loaded = False


def _ensure_loaded():
    global _data, _loaded
    if _loaded:
        return
    _loaded = True

    # 1) 尝试从本地缓存加载
    if os.path.exists(CACHE_FILE):
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            if time.time() - mtime < CACHE_TTL:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    _data = json.load(f)
                print(f"[MooshieData] 从本地缓存加载 {len(_data)} 个画师")
                return
        except Exception:
            pass

    # 2) 从 CDN 下载
    print(f"[MooshieData] 从 CDN 下载 {SEARCH_URL} ...")
    try:
        resp = requests.get(SEARCH_URL, timeout=60)
        resp.raise_for_status()
        _data = resp.json()
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_data, f)
        print(f"[MooshieData] 下载完成，缓存 {len(_data)} 个画师")
    except Exception as e:
        print(f"[MooshieData] 下载失败: {e}")
        _data = []


def search(query, limit=36, page=1, sort="count"):
    """
    搜索画师，返回格式兼容原版 animadex API：
    {results: [{name, slug, thumb_url, trigger, count, fav_count, tags}], total}
    """
    _ensure_loaded()
    results = list(_data) if _data else []

    # 过滤
    q = query.strip().lower() if query else ""
    if q:
        results = [
            a for a in results
            if q in a["tag"].lower() or q in a["slug"].lower()
        ]

    total = len(results)

    # 排序
    if sort == "random":
        import random
        random.shuffle(results)
    else:
        results.sort(key=lambda a: -a.get("postCount", 0))

    # 分页
    start = (page - 1) * limit
    page_results = results[start:start + limit]

    # 映射到原版 API 格式
    mapped = []
    for a in page_results:
        image_id = a.get("imageId", "")
        tag = a.get("tag", "")
        # 去掉 @ 前缀作为 name/trigger
        trigger = tag.lstrip("@") if tag else ""
        mapped.append({
            "name": trigger,
            "slug": a.get("slug", ""),
            "thumb_url": f"{IMAGE_BASE}/{image_id}.avif" if image_id else "",
            "trigger": trigger,
            "count": a.get("postCount", 0),
            "fav_count": a.get("postCount", 0) // 3,
            "tags": [],
            "copyright_name": "",
        })

    return mapped, total


def get_facets():
    """Mooshie 没有 facet 数据，返回空"""
    return {}
