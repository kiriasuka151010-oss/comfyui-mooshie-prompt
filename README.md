# ComfyUI Mooshie Prompt

> 简化版 D 站 Prompt Pipeline — 艺术家浏览 → 标签拆分 → Prompt 构建 → 手动微调

## 四个节点

| 节点 | 作用 | 输入 | 输出 |
|------|------|------|------|
| **MooshieBrowser** | 从 Mooshieblob 画廊选艺术家 | — | `@artist_tag` |
| **DanbooruTagSplitter** | 拉 D 站图片，拆分标签 | artist_tag | 角色/画师/姿势 + 预览图 |
| **AnimaPromptBuilder** | 组装 Anima 格式 prompt | 角色/画师/姿势 | prompt 字符串 |
| **EditablePrompt** | 开关切换自动/手动 prompt | prompt + 手动文本 | 最终 prompt |

## 安装

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/kiriasuka151010-oss/comfyui-mooshie-prompt.git
```

重启 ComfyUI，在节点菜单中找到 `mooshie` 分类。

## 工作流

```
MooshieBrowser → DanbooruTagSplitter → AnimaPromptBuilder → EditablePrompt → CLIPTextEncode
```

拖入 `workflows/smoke-test.json` 测试。

## 与 Batch Debug 配合

EditablePrompt 输出接 CLIPTextEncode → BatchDebugExecute（conditioning 模式），即可批量对比不同 LoRA/CFG 参数。
