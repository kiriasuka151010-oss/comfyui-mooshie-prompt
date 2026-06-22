"""
EditablePrompt v4 — 逐类跟随/锁定开关 + JS 自动同步
"""
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

import json

QUALITY_DEFAULT = "masterpiece, best quality, score_9, year 2025, highres, official art, sensitive"

CATEGORIES = ["quality", "artist", "character", "series", "general", "meta"]
CAT_LABELS = {"quality":"质量词","artist":"画师","character":"角色","series":"系列","general":"常规","meta":"元标签"}


class EditablePrompt:
    @classmethod
    def INPUT_TYPES(cls):
        required = {}
        for cat in CATEGORIES:
            required[f"mode_{cat}"] = (["跟随", "锁定"], {"default": "跟随"})
            default_val = QUALITY_DEFAULT if cat == "quality" else ""
            placeholder = CAT_LABELS[cat] + ("（锁定后可编辑）" if cat != "quality" else "")
            required[cat] = ("STRING", {
                "multiline": True, "default": default_val,
                "placeholder": placeholder
            })
        return {
            "required": required,
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

    def edit(self, upstream_data="", upstream_prompt="", **kwargs):
        if upstream_prompt.strip():
            return (upstream_prompt, upstream_prompt)

        upstream = {}
        if upstream_data.strip():
            try:
                upstream = json.loads(upstream_data)
            except json.JSONDecodeError:
                pass

        resolved = {}
        for cat in CATEGORIES:
            mode = kwargs.get(f"mode_{cat}", "跟随")
            manual_val = kwargs.get(cat, "").strip()
            upstream_val = upstream.get(cat, "")
            if mode == "锁定":
                resolved[cat] = manual_val
            else:
                resolved[cat] = upstream_val

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


NODE_CLASS_MAPPINGS["EditablePrompt"] = EditablePrompt
NODE_DISPLAY_NAME_MAPPINGS["EditablePrompt"] = "Editable Prompt (逐类锁定/跟随)"
