"""
comfyui-mooshie-prompt
Mooshie Browser + Danbooru Tag Splitter + Anima Prompt Builder + Editable Prompt
"""

import sys, os
plugin_dir = os.path.dirname(os.path.abspath(__file__))
py_dir = os.path.join(plugin_dir, "py")
if py_dir not in sys.path:
    sys.path.insert(0, py_dir)

from .py.mooshie_browser import NODE_CLASS_MAPPINGS as mb_mappings
from .py.mooshie_browser import NODE_DISPLAY_NAME_MAPPINGS as mb_display
from .py.danbooru_splitter import NODE_CLASS_MAPPINGS as ds_mappings
from .py.danbooru_splitter import NODE_DISPLAY_NAME_MAPPINGS as ds_display
from .py.anima_builder import NODE_CLASS_MAPPINGS as ab_mappings
from .py.anima_builder import NODE_DISPLAY_NAME_MAPPINGS as ab_display
from .py.editable_prompt import NODE_CLASS_MAPPINGS as ep_mappings
from .py.editable_prompt import NODE_DISPLAY_NAME_MAPPINGS as ep_display

from .py.mooshie_browser import register_routes as register_mb_routes
from .py.danbooru_splitter import register_routes as register_ds_routes
register_mb_routes()
register_ds_routes()

NODE_CLASS_MAPPINGS = {}
NODE_CLASS_MAPPINGS.update(mb_mappings)
NODE_CLASS_MAPPINGS.update(ds_mappings)
NODE_CLASS_MAPPINGS.update(ab_mappings)
NODE_CLASS_MAPPINGS.update(ep_mappings)

NODE_DISPLAY_NAME_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS.update(mb_display)
NODE_DISPLAY_NAME_MAPPINGS.update(ds_display)
NODE_DISPLAY_NAME_MAPPINGS.update(ab_display)
NODE_DISPLAY_NAME_MAPPINGS.update(ep_display)

WEB_DIRECTORY = "./js"

print(f"[MooshiePrompt] {len(NODE_CLASS_MAPPINGS)} nodes loaded")
for name in NODE_CLASS_MAPPINGS:
    print(f"  ├── {name}")
