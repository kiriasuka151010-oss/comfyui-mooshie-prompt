"""
EditablePrompt v3 — 单线连接 + 逐类锁定/跟随
接 MooshieBrowser 的 tag_data 输出（一根线），6类各自可锁可跟
"""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

QUALITY_DEFAULT = "masterpiece, best quality, score_9, year 2025, highres, official art, sensitive"

CATEGORIES = ["quality", "artist", "character", "series", "general", "meta"]


class EditablePrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "quality": ("STRING", {
                    "multiline": True, "default": QUALITY_DEFAULT,
                    "placeholder": "质量词（清空则跟随上游）"
                }),
                "artist": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "画师（留空=跟随上游，填了=锁定）"
                }),
                "character": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "角色（留空=跟随上游）"
                }),
                "series": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "系列出处（留空=跟随上游）"
                }),
                "general": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "常规标签（留空=跟随上游）"
                }),
                "meta": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "元标签（留空=跟随上游）"
                }),
            },
            "optional": {
                "upstream_data": ("STRING", {
                    "multiline": False, "defaultInput": True, "forceInput": True
                }),
                "upstream_prompt": ("STRING", {
                    "multiline": False, "defaultInput": True, "forceInput": True
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "preview")
    FUNCTION = "edit"
    CATEGORY = "mooshie"

    def edit(self, quality, artist, character, series, general, meta,
             upstream_data="", upstream_prompt=""):
        # ── 上游有整段 prompt → 直接透传（向后兼容） ──
        if upstream_prompt.strip():
            return (upstream_prompt, upstream_prompt)

        # ── 解析上游 JSON 数据 ──
        upstream = {}
        if upstream_data.strip():
            try:
                upstream = json.loads(upstream_data)
            except json.JSONDecodeError:
                pass

        # ── 手动值字典 ──
        manual = {
            "quality": quality.strip(),
            "artist": artist.strip(),
            "character": character.strip(),
            "series": series.strip(),
            "general": general.strip(),
            "meta": meta.strip(),
        }

        # ── 逐类决定：lock 还是 follow ──
        resolved = {}
        for cat in CATEGORIES:
            mv = manual[cat]
            uv = upstream.get(cat, "")
            if mv:
                resolved[cat] = mv  # locked
            else:
                resolved[cat] = uv  # follow upstream

        # ── 拼合 prompt ──
        parts = [resolved["quality"]]
        if resolved["character"]:
            parts.append(resolved["character"])
        if resolved["artist"]:
            tags = resolved["artist"].replace(",", " ").split()
            atags = [t if t.startswith("@") else f"@{t}" for t in tags if t]
            parts.append(" ".join(atags))
        if resolved["series"]:
            parts.append(resolved["series"])
        if resolved["general"]:
            parts.append(resolved["general"])
        if resolved["meta"]:
            parts.append(resolved["meta"])

        result = ", ".join(p for p in parts if p)
        return (result, result)


# 需要用 json，import 放最上面
import json

NODE_CLASS_MAPPINGS["EditablePrompt"] = EditablePrompt
NODE_DISPLAY_NAME_MAPPINGS["EditablePrompt"] = "Editable Prompt (逐类锁定/跟随)"
