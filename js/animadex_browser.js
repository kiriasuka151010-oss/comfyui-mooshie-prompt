import { app } from "/scripts/app.js";

app.registerExtension({
    name: "Comfy.MooshieBrowser",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MooshieBrowser") return;

        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onCreated?.apply(this, arguments);
            this.setSize([800, 750]);
            this.title = "Mooshie 艺术家浏览器 (Mooshie Browser)";
            this.onDrawBackground = function() {
                const el = this.nodeEl?.querySelector?.(".comfy-title");
                if (el && el.style.fontSize !== "16px") {
                    el.style.fontSize = "16px";
                    el.style.fontWeight = "bold";
                }
            };
            this.isChanged = true;
            const node = this;

            // ── _tag widget ──
            const tagW = node.widgets?.find(w => w.name === "_tag");
            if (tagW) { tagW.computeSize = () => [0.1, 20]; tagW.serialize = true; }

            let sortMode = "count";
            let results = [];
            let page = 1;
            let totalResults = 0;
            let _searchTimer = null;

            const el = document.createElement("div");
            el.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;background:#1a1a2e;border-radius:6px;min-height:0;";

            // ── 顶栏 ──
            const bar = document.createElement("div");
            bar.style.cssText = "display:flex;gap:6px;padding:8px;align-items:center;border-bottom:1px solid #0f3460;flex-shrink:0;";

            // 排序按钮
            const sortBtns = {};
            for (const [sk, sl] of [["count","🔥 热门"],["fav_count","❤️ 最多喜欢"],["random","🔀 随机"]]) {
                const sb = document.createElement("button");
                sb.textContent = sl;
                sb.style.cssText = `padding:5px 8px;border-radius:4px;border:none;cursor:pointer;font-size:11px;background:${sk===sortMode?"#0f3460":"transparent"};color:${sk===sortMode?"#4fc3f7":"#888"};`;
                sb.onclick = () => {
                    sortMode = sk;
                    page = 1;
                    for (const [k,v] of Object.entries(sortBtns)) { v.style.background = k===sortMode?"#0f3460":"transparent"; v.style.color = k===sortMode?"#4fc3f7":"#888"; }
                    if (inp.value.trim()) { clearTimeout(_searchTimer); search(); }
                    else doSearch("");
                };
                sortBtns[sk] = sb;
                bar.appendChild(sb);
            }

            const inp = document.createElement("input");
            inp.type = "text";
            inp.placeholder = "搜索画师名...";
            inp.style.cssText = "flex:1;padding:6px 10px;border-radius:4px;border:1px solid #0f3460;background:#16213e;color:#e0e0e0;font-size:13px;outline:none;";

            // 自动补全
            const acList = document.createElement("div");
            acList.style.cssText = "display:none;position:absolute;top:100%;left:0;right:0;background:#1a1a2e;border:1px solid #0f3460;border-radius:0 0 4px 4px;max-height:240px;overflow-y:auto;z-index:999;";
            bar.style.position = "relative";
            let _acTimer = null;

            function showAc(items) {
                acList.innerHTML = "";
                if (!items || !items.length) { acList.style.display = "none"; return; }
                for (const r of items) {
                    const row = document.createElement("div");
                    const name = r.name || "";
                    row.style.cssText = "padding:5px 8px;cursor:pointer;color:#b0bec5;font-size:12px;border-bottom:1px solid #0f3460;display:flex;gap:6px;align-items:center;";
                    row.onmouseover = () => row.style.background = "#0d2137";
                    row.onmouseout = () => row.style.background = "transparent";
                    row.onclick = () => {
                        inp.value = name;
                        acList.style.display = "none";
                        page = 1;
                        doSearch(name);
                    };
                    const nm = document.createElement("span");
                    nm.textContent = name;
                    nm.style.cssText = "font-weight:bold;color:#e0e0e0;font-size:12px;";
                    row.appendChild(nm);
                    acList.appendChild(row);
                }
                acList.style.display = "block";
            }

            inp.oninput = () => {
                const q = inp.value.trim();
                if (!q) { acList.style.display = "none"; clearTimeout(_searchTimer); return; }
                clearTimeout(_acTimer);
                _acTimer = setTimeout(async () => {
                    acList.innerHTML = '<div style="padding:8px;text-align:center;color:#666;font-size:11px;">⏳ 搜索建议...</div>';
                    acList.style.display = "block";
                    try {
                        const r = await fetch("/mooshie/search", {
                            method: "POST", headers: {"Content-Type":"application/json"},
                            body: JSON.stringify({mode:"artists", query: q, page: 1}),
                        });
                        const d = await r.json();
                        showAc((d.results || []).slice(0, 10));
                    } catch { acList.style.display = "none"; }
                }, 150);
            };
            inp.onkeydown = (e) => {
                if (e.key === "Enter") { acList.style.display = "none"; clearTimeout(_searchTimer); search(); }
                if (e.key === "Escape") acList.style.display = "none";
            };
            inp.onblur = () => setTimeout(() => acList.style.display = "none", 200);

            const sBtn = document.createElement("button");
            sBtn.textContent = "🔍";
            sBtn.style.cssText = "padding:5px 14px;border-radius:4px;border:none;background:#e94560;color:#fff;cursor:pointer;font-size:16px;";
            sBtn.onclick = search;
            bar.append(inp, acList, sBtn);

            // ── 提示栏 ──
            const hint = document.createElement("div");
            hint.style.cssText = "padding:4px 10px;font-size:11px;color:#888;border-bottom:1px solid #0f3460;flex-shrink:0;";
            hint.textContent = "💡 点击卡片选中 → 输出 @artist_tag → 直连 D站搜索";

            // ── 网格 ──
            const grid = document.createElement("div");
            grid.style.cssText = "flex:1;min-height:0;overflow-y:auto;padding:6px;display:flex;flex-wrap:wrap;gap:6px;align-content:flex-start;";

            // ── 翻页栏 ──
            const pageBar = document.createElement("div");
            pageBar.style.cssText = "display:none;justify-content:center;align-items:center;gap:8px;padding:6px 8px;border-top:1px solid #0f3460;flex-shrink:0;font-size:12px;";

            function goPage(p) {
                page = p;
                const q = inp.value.trim();
                doSearch(q);
            }

            function renderPage(total) {
                totalResults = total;
                const totalPages = Math.ceil(totalResults / 36);
                if (totalPages <= 1) { pageBar.style.display = "none"; return; }
                pageBar.style.display = "flex";
                pageBar.innerHTML = "";
                const prev = document.createElement("span");
                prev.textContent = "◀ 上一页";
                prev.style.cssText = `cursor:${page>1?"pointer":"default"};color:${page>1?"#4fc3f7":"#444"};font-size:11px;`;
                if (page > 1) prev.onclick = () => goPage(page - 1);
                pageBar.appendChild(prev);
                const start = Math.max(1, page - 2);
                const end = Math.min(totalPages, page + 2);
                if (start > 1) { const e = document.createElement("span"); e.textContent = "..."; e.style.cssText = "color:#666;font-size:11px;"; pageBar.appendChild(e); }
                for (let i = start; i <= end; i++) {
                    const pn = document.createElement("span");
                    pn.textContent = i;
                    pn.style.cssText = `cursor:pointer;padding:1px 7px;border-radius:3px;font-size:11px;background:${i===page?"#e94560":"transparent"};color:${i===page?"#fff":"#aaa"};`;
                    if (i !== page) pn.onclick = () => goPage(i);
                    pageBar.appendChild(pn);
                }
                if (end < totalPages) { const e = document.createElement("span"); e.textContent = "..."; e.style.cssText = "color:#666;font-size:11px;"; pageBar.appendChild(e); }
                const next = document.createElement("span");
                next.textContent = "下一页 ▶";
                next.style.cssText = `cursor:${page<totalPages?"pointer":"default"};color:${page<totalPages?"#4fc3f7":"#444"};font-size:11px;`;
                if (page < totalPages) next.onclick = () => goPage(page + 1);
                pageBar.appendChild(next);
            }

            function render() {
                grid.innerHTML = "";
                if (!results.length) {
                    pageBar.style.display = "none";
                    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:60px 20px;color:#888;"><div style="font-size:48px;margin-bottom:12px;">🔍</div><div style="font-size:15px;color:#aaa;">输入关键词搜索 Mooshie 艺术家（42k+ 画师）</div></div>';
                    return;
                }
                for (const r of results) {
                    const name = r.name || "";
                    const slug = r.slug || "";
                    const trig = r.trigger || "";
                    const thumbUrl = r.thumb_url || "";

                    const copyTagAt = "@" + (trig || name);
                    const dbTag = r.slug || trig || name;

                    const card = document.createElement("div");
                    card.style.cssText = "background:#0f3460;border-radius:6px;overflow:hidden;cursor:pointer;border:2px solid transparent;width:calc(33.333% - 6px);flex-shrink:0;box-sizing:border-box;";
                    card.onclick = () => {
                        grid.querySelectorAll(".ad-sel").forEach(c => { c.style.borderColor = "transparent"; c.classList.remove("ad-sel"); });
                        card.style.borderColor = "#e94560"; card.classList.add("ad-sel");
                    };

                    // 预览图
                    const imgDiv = document.createElement("div");
                    imgDiv.style.cssText = "width:100%;background:#16213e;display:flex;align-items:center;justify-content:center;aspect-ratio:1;";
                    if (thumbUrl) {
                        const img = new Image();
                        img.style.cssText = "width:100%;height:100%;object-fit:cover;display:block;";
                        img.src = "/mooshie/image?url=" + encodeURIComponent(thumbUrl);
                        img.onerror = function() { this.style.display = "none"; this.parentElement.textContent = "🖼"; this.parentElement.style.fontSize = "28px"; this.parentElement.style.color = "#555"; };
                        imgDiv.appendChild(img);
                    } else { imgDiv.textContent = "🖼"; imgDiv.style.fontSize = "28px"; imgDiv.style.color = "#555"; }

                    // 信息
                    const info = document.createElement("div");
                    info.style.cssText = "padding:4px 6px;font-size:11px;color:#b0bec5;line-height:1.4;";
                    let html = `<div style="font-weight:bold;color:#e0e0e0;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${name}</div>`;
                    html += `<div style="color:#888;font-size:10px;">📊 ${r.count || 0} posts</div>`;
                    info.innerHTML = html;

                    // 复制按钮
                    const btnRow = document.createElement("div");
                    btnRow.style.cssText = "display:flex;gap:3px;margin-top:3px;";
                    const copyBtn = document.createElement("button");
                    copyBtn.textContent = "📋 复制 @" + (trig || name);
                    copyBtn.style.cssText = "flex:1;padding:3px 0;border:none;border-radius:3px;background:#e94560;color:#fff;cursor:pointer;font-size:10px;text-align:center;";
                    copyBtn.onclick = (e) => {
                        e.stopPropagation();
                        navigator.clipboard.writeText(copyTagAt).then(() => {
                            copyBtn.textContent = "✅";
                            setTimeout(() => { copyBtn.textContent = "📋 复制 @" + (trig || name); }, 1500);
                        });
                    };
                    btnRow.appendChild(copyBtn);
                    info.appendChild(btnRow);

                    // 去 D站搜索
                    const dbBtn = document.createElement("button");
                    dbBtn.textContent = "🔍 去 D站搜索";
                    dbBtn.style.cssText = "display:block;width:100%;padding:3px 0;margin-top:2px;border:none;border-radius:3px;background:#0f3460;color:#4fc3f7;cursor:pointer;font-size:10px;text-align:center;";
                    dbBtn.onclick = (e) => {
                        e.stopPropagation();
                        if (tagW) { tagW.value = dbTag; }
                        node.isChanged = true;
                        for (const n of (app.graph._nodes || [])) {
                            if (n.type === "DanbooruBrowser") {
                                const el = n.nodeEl?.querySelector?.("input[type='text']");
                                if (el) { el.value = dbTag; el.dispatchEvent(new Event("input", {bubbles:true})); el.dispatchEvent(new KeyboardEvent("keydown", {key:"Enter", bubbles:true})); }
                                const aw = n.widgets?.find(w => w.name === "来自AnimaDex");
                                if (aw) { aw.value = dbTag; }
                            }
                        }
                        dbBtn.textContent = "✅ 已发送";
                        setTimeout(() => { dbBtn.textContent = "🔍 去 D站搜索"; }, 1500);
                    };
                    info.appendChild(dbBtn);

                    card.append(imgDiv, info);
                    grid.appendChild(card);
                }
            }

            async function doSearch(q) {
                grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:#888;">⏳ 搜索中...</div>';
                pageBar.style.display = "none";
                try {
                    const r = await fetch("/mooshie/search", {
                        method: "POST", headers: {"Content-Type":"application/json"},
                        body: JSON.stringify({mode:"artists", query: q, page, sort: sortMode}),
                    });
                    const d = await r.json();
                    results = d.results || [];
                    renderPage(d.total || 0);
                } catch { results = []; }
                render();
            }

            async function search() {
                page = 1;
                const q = inp.value.trim();
                if (q) doSearch(q);
            }

            el.append(bar, hint, grid, pageBar);
            this.addDOMWidget("animadex_ui", "div", el, { onDraw: () => {} });

            doSearch("");
        };
    },
});
