# ComfyUI Mooshie Prompt

> 轻量增量 — 在 ComfyUI-Danbooru-Anima-Prompt 原版节点基础上，加 EditablePrompt

## 依赖

必须先安装 [ComfyUI-Danbooru-Anima-Prompt](https://github.com/...)。

本插件不重复打包原版节点，直接从原版导入。

## 节点

| 节点 | 来源 | 作用 |
|------|------|------|
| **AnimaDexBrowser** | 原版 | 浏览 AnimaDex 画廊，选角色/画师，看图选风格 |
| **DanbooruBrowser** | 原版 | 拉 D 站图片，拆分标签，浏览搜索 |
| **AnimaPromptConverter** | 原版 | 组装 Anima 格式 prompt |
| **EditablePrompt** | 🆕 本插件 | 开关切换自动/手动 prompt，上游来的自动透传，切手动自由编辑 |

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kiriasuka151010-oss/comfyui-mooshie-prompt.git
```

**前提：** 已安装 `ComfyUI-Danbooru-Anima-Prompt` 原版插件。

重启 ComfyUI，在节点菜单找到 `mooshie` 分类下的 EditablePrompt。

## 工作流

```
AnimaDexBrowser → DanbooruBrowser → AnimaPromptConverter → EditablePrompt → CLIPTextEncode
```

- **自动模式：** 上游 prompt 直接透传，不受干扰
- **手动模式：** 切换到手动，自由编辑 prompt 文本

## 为什么是轻量增量

原版插件的画廊浏览、图片搜索、LLM 模糊搜索等功能完整保留。本插件只加一个 EditablePrompt，不做重复工作。
