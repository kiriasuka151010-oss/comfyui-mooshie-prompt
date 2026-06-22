"""
EditablePrompt — 可编辑提示词
支持分段编辑（画师/角色/常规）或整体 prompt，跳过 AnimaPromptConverter
"""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

QUALITY_DEFAULT = "masterpiece, best quality, score_9, year 2025, highres, official art, sensitive"


class EditablePrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "source": (["upstream", "manual"], {"default": "upstream"}),
                "quality": ("STRING", {
                    "multiline": True, "default": QUALITY_DEFAULT,
                    "placeholder": "质量词 (score_9, masterpiece...)"
                }),
                "artist": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "画师标签 (手动模式下编辑, 上游有输入时被覆盖)"
                }),
                "character": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "角色标签"
                }),
                "general": ("STRING", {
                    "multiline": True, "default": "",
                    "placeholder": "常规标签 (动作/服装/场景/表情...)"
                }),
            },
            "optional": {
                "upstream_prompt": ("STRING", {
                    "multiline": False, "defaultInput": True, "forceInput": True
                }),
                "upstream_artist": ("STRING", {
                    "multiline": False, "defaultInput": True, "forceInput": True
                }),
                "upstream_character": ("STRING", {
                    "multiline": False, "defaultInput": True, "forceInput": True
                }),
                "upstream_general": ("STRING", {
                    "multiline": False, "defaultInput": True, "forceInput": True
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "preview")
    FUNCTION = "edit"
    CATEGORY = "mooshie"

    def edit(self, source, quality, artist, character, general,
             upstream_prompt="", upstream_artist="", upstream_character="", upstream_general=""):
        # ── upstream 模式 ──
        if source == "upstream":
            # 1) 有整体 upstream_prompt → 直接透传
            if upstream_prompt.strip():
                result = upstream_prompt
            # 2) 有分段输入 → 拼合
            else:
                a = upstream_artist.strip()
                c = upstream_character.strip()
                g = upstream_general.strip()
                parts = [quality.strip()]
                if c:
                    parts.append(c)
                if a:
                    tags = a.replace(",", " ").split()
                    atags = [t if t.startswith("@") else f"@{t}" for t in tags if t]
                    parts.append(" ".join(atags))
                if g:
                    parts.append(g)
                result = ", ".join(parts)
            return (result, result)

        # ── manual 模式 ──
        a = artist.strip()
        c = character.strip()
        g = general.strip()
        parts = [quality.strip()]
        if c:
            parts.append(c)
        if a:
            tags = a.replace(",", " ").split()
            atags = [t if t.startswith("@") else f"@{t}" for t in tags if t]
            parts.append(" ".join(atags))
        if g:
            parts.append(g)
        result = ", ".join(parts)
        return (result, result)


NODE_CLASS_MAPPINGS["EditablePrompt"] = EditablePrompt
NODE_DISPLAY_NAME_MAPPINGS["EditablePrompt"] = "Editable Prompt (可编辑提示词)"
