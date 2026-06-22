"""
AnimaPromptBuilder — 简化版 Prompt 构建器
输入: 角色 / 画师 / 姿势 tag
输出: Anima 格式 prompt 字符串
"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

class AnimaPromptBuilder:
    """Build Anima-format prompt from character, artist, and pose tags."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "quality_prefix": ("STRING", {
                    "multiline": False,
                    "default": "masterpiece, best quality, score_9, year 2025, highres, official art, sensitive",
                    "tooltip": "Quality tags prepended to every prompt."
                }),
            },
            "optional": {
                "character_tags": ("STRING", {
                    "multiline": False,
                    "defaultInput": True,
                    "forceInput": True,
                    "tooltip": "Character tags from DanbooruTagSplitter."
                }),
                "artist_tags": ("STRING", {
                    "multiline": False,
                    "defaultInput": True,
                    "forceInput": True,
                    "tooltip": "Artist tags from DanbooruTagSplitter."
                }),
                "pose_tags": ("STRING", {
                    "multiline": False,
                    "defaultInput": True,
                    "forceInput": True,
                    "tooltip": "Pose/action tags from DanbooruTagSplitter."
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "mooshie"
    DESCRIPTION = "Build Anima prompt from character/artist/pose tags."

    def build(self, quality_prefix, character_tags="", artist_tags="", pose_tags=""):
        parts = [quality_prefix.strip()]
        if character_tags.strip():
            parts.append(character_tags.strip())
        if pose_tags.strip():
            parts.append(pose_tags.strip())
        if artist_tags.strip():
            # Artist tags should have @ prefix for Anima
            artists = artist_tags.strip()
            if not artists.startswith("@"):
                artists = "@" + artists.replace(", ", ",@").replace(",", ",@")
            parts.append(artists)
        prompt = ", ".join(p for p in parts if p)
        return (prompt,)


NODE_CLASS_MAPPINGS["AnimaPromptBuilder"] = AnimaPromptBuilder
NODE_DISPLAY_NAME_MAPPINGS["AnimaPromptBuilder"] = "Anima Prompt Builder (提示词构建)"
