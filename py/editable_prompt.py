"""
EditablePrompt — 可编辑 Prompt 节点
默认显示上游传来的 prompt，可手动修改。
开关切换「用上游」/「用手动」。
"""

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

class EditablePrompt:
    """A prompt node that shows upstream prompt and allows manual editing."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Prompt text. Automatically filled from upstream if connected."
                }),
                "source": (["upstream", "manual"], {
                    "default": "upstream",
                    "tooltip": "'upstream' uses connected prompt input. 'manual' uses the text you type here."
                }),
            },
            "optional": {
                "upstream_prompt": ("STRING", {
                    "multiline": False,
                    "defaultInput": True,
                    "forceInput": True,
                    "tooltip": "Connect from AnimaPromptBuilder or any prompt source."
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "edit"
    CATEGORY = "mooshie"
    DESCRIPTION = "Edit prompt manually or pass through upstream. Toggle source with dropdown."

    def edit(self, text, source, upstream_prompt=""):
        if source == "upstream" and upstream_prompt.strip():
            return (upstream_prompt,)
        return (text,)


NODE_CLASS_MAPPINGS["EditablePrompt"] = EditablePrompt
NODE_DISPLAY_NAME_MAPPINGS["EditablePrompt"] = "Editable Prompt (可编辑提示词)"
