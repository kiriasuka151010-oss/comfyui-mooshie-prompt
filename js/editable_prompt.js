import { app } from "/scripts/app.js";

const CATEGORIES = ["quality", "artist", "character", "series", "general", "meta"];

app.registerExtension({
    name: "Comfy.EditablePrompt",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "EditablePrompt") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            const node = this;

            // 隐藏所有 mode_* 和 upstream 相关的 widget（只留可编辑的）
            const widgets = node.widgets || [];
            for (const w of widgets) {
                if (w.name === "upstream_data") {
                    w.computeSize = () => [0.1, 20];
                }
            }

            // 找到 upstream_data widget
            const upW = node.widgets?.find(w => w.name === "upstream_data");

            // 定时检查上游数据变化 → 同步到"跟随"模式的框里
            let _lastUpstream = "";
            const _sync = () => {
                if (!upW) { setTimeout(_sync, 500); return; }
                const val = (upW.value || "").trim();
                if (val === _lastUpstream) { setTimeout(_sync, 500); return; }
                _lastUpstream = val;

                let upstream = {};
                if (val) {
                    try { upstream = JSON.parse(val); } catch (e) {}
                }

                for (const cat of CATEGORIES) {
                    const modeW = node.widgets?.find(w => w.name === `mode_${cat}`);
                    const textW = node.widgets?.find(w => w.name === cat);
                    if (!modeW || !textW) continue;
                    if (modeW.value === "跟随") {
                        const uv = upstream[cat] || "";
                        if (textW.value !== uv) {
                            textW.value = cat === "quality" && !uv ? textW.value : uv;
                            if (textW.callback) textW.callback(uv);
                        }
                    }
                }
                node.setDirtyCanvas(true);
                setTimeout(_sync, 500);
            };
            setTimeout(_sync, 500);

            // mode 切换时：切到锁定→不清空；切到跟随→立即同步上游
            for (const cat of CATEGORIES) {
                const modeW = node.widgets?.find(w => w.name === `mode_${cat}`);
                if (!modeW) continue;
                const origCb = modeW.callback;
                modeW.callback = function (val) {
                    if (origCb) origCb.call(this, val);
                    if (val === "跟随") {
                        let upstream = {};
                        try { upstream = JSON.parse((upW?.value || "").trim()); } catch (e) {}
                        const textW = node.widgets?.find(w => w.name === cat);
                        if (textW) {
                            textW.value = upstream[cat] || (cat === "quality" ? textW.value : "");
                            if (textW.callback) textW.callback(textW.value);
                        }
                    }
                    node.setDirtyCanvas(true);
                };
            }
        };
    },
});
