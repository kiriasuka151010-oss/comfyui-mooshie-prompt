# comfyui-mooshie-prompt

> Mooshie 画师浏览 + Danbooru 标签搜索 + 可编辑 Prompt — 一根线搞定

[中文介绍](README.html)

## 节点

| 节点 | 作用 |
|------|------|
| **MooshieBrowser** | 上半浏览 42k+ Mooshie 画师，下半搜索 D站 画廊，瀑布流展示，一键输出标签 |
| **EditablePrompt** | 6 类标签（质量/画师/角色/系列/常规/元），每类独立跟随/锁定开关 |

## 特性

- 🎨 Mooshie 画师浏览 — CDN 缩略图预览，搜索/排序 42k+ AI 风格画师
- 📋 D站 标签搜索 — 中文/英文模糊 tag 联想（50k+ 标签索引）
- 🏷️ 5 类原生标签 — 画师 / 角色 / 系列 / 常规 / 元，Danbooru 官方分类
- 🔒 逐类跟随/锁定 — 每类独立开关，跟随=同步上游，锁定=手动改
- ❤️ 收藏系统 — 保存喜欢的 D站 图，一键复用
- 📱 瀑布流画廊 — 原比例展示，竖图高横图矮
- 🖼️ 双击大图 — 原图+下载
- 🔞 分级过滤 — S/Q/E 三键切换
- 🔗 单线连接 — MooshieBrowser 只输出一根 tag_data，EditablePrompt 只接一根 upstream_data

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kiriasuka151010-oss/comfyui-mooshie-prompt.git
```

重启 ComfyUI，拖入 `workflows/smoke-test.json` 即可开始。

**依赖：** 中文标签索引首次启动自动从同目录的 `ComfyUI-Danbooru-Anima-Prompt` 加载，无需额外配置。

## 工作流

**smoke-test.json** — 基础测试

```
MooshieBrowser → EditablePrompt → CLIPTextEncode → KSampler → VAEDecode → SaveImage
```

**baselinelora.json** — LoRA 生产

```
MooshieBrowser → EditablePrompt → CLIPTextEncode → Power LoRA Loader → KSampler → VAEDecode → SaveImage
```

anima_baseV10 + 26 个 Anima LoRA，768×1536 竖版，预调参数。

## 可选依赖

- Power LoRA Loader（rgthree-comfy）— baselinelora.json 需要
- PreviewAny（comfy-core）— prompt 预览
