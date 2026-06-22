"""
comfyui-mooshie-prompt
MooshieBrowser — 浏览 Mooshieblob 42k+ 艺术家画廊 + EditablePrompt 微调
"""
import sys, os

plugin_dir = os.path.dirname(os.path.abspath(__file__))
py_dir = os.path.join(plugin_dir, "py")
if py_dir not in sys.path:
    sys.path.insert(0, py_dir)

from .py.animadex_browser import NODE_CLASS_MAPPINGS as ad_mappings
from .py.animadex_browser import NODE_DISPLAY_NAME_MAPPINGS as ad_display
from .py.animadex_browser import register_routes as register_ad_routes
from .py.editable_prompt import NODE_CLASS_MAPPINGS as ep_mappings
from .py.editable_prompt import NODE_DISPLAY_NAME_MAPPINGS as ep_display

register_ad_routes()

NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(ad_mappings)
NODE_CLASS_MAPPINGS.update(ep_mappings)

NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(ad_display)
NODE_DISPLAY_NAME_MAPPINGS.update(ep_display)

WEB_DIRECTORY = "./js"

print(f"[MooshiePrompt] {len(NODE_CLASS_MAPPINGS)} nodes loaded")
for name in NODE_CLASS_MAPPINGS:
    print(f"  ├── {name}")
