import { app } from "/scripts/app.js";

app.registerExtension({
    name: "Comfy.MooshieBrowser",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "MooshieBrowser") return;

        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onCreated?.apply(this, arguments);
            this.setSize([800, 1000]);
            this.title = "Mooshie 画师 + D站 (Mooshie Browser)";
            this.isChanged = true;
            const node = this;

            // ── widgets ──
            const tagW = node.widgets?.find(w => w.name === "_tag");
            if (tagW) { tagW.computeSize = () => [0.1, 20]; tagW.serialize = true; }
            const selW = node.widgets?.find(w => w.name === "selection_data");
            if (selW) { selW.computeSize = () => [0.1, 20]; selW.serialize = true; }

            // ── state ──
            let sortMode = "count";
            let artists = [];
            let artistPage = 1;
            let artistTotal = 0;
            let posts = [];
            let selectedPost = null;
            let selectedArtist = null;
            let _searchTimer = null;

            const root = document.createElement("div");
            root.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;background:#1a1a2e;border-radius:6px;min-height:0;";

            // ═══════════════════════════════════════════
            //  上半：画师浏览
            // ═══════════════════════════════════════════

            const topPanel = document.createElement("div");
            topPanel.style.cssText = "flex:0 0 auto;display:flex;flex-direction:column;border-bottom:2px solid #e94560;";

            // 顶栏
            const topBar = document.createElement("div");
            topBar.style.cssText = "display:flex;gap:6px;padding:8px;align-items:center;flex-shrink:0;";
            topBar.innerHTML = '<span style="color:#e94560;font-weight:bold;font-size:13px;">🎨 画师浏览</span>';
            topBar.style.cssText += "border-bottom:1px solid #0f3460;";

            const sortBtns = {};
            for (const [sk, sl] of [["count","🔥"],["fav_count","❤️"],["random","🔀"]]) {
                const sb = document.createElement("button");
                sb.textContent = sl;
                sb.title = sk==="count"?"热门":sk==="fav_count"?"最多喜欢":"随机";
                sb.style.cssText = `padding:3px 6px;border-radius:3px;border:none;cursor:pointer;font-size:11px;background:${sk===sortMode?"#e94560":"#2a2a3a"};color:${sk===sortMode?"#fff":"#888"};`;
                sb.onclick = () => {
                    sortMode = sk; artistPage = 1;
                    for (const [k,v] of Object.entries(sortBtns)) { v.style.background = k===sortMode?"#e94560":"#2a2a3a"; v.style.color = k===sortMode?"#fff":"#888"; }
                    loadArtists();
                };
                sortBtns[sk] = sb;
                topBar.appendChild(sb);
            }

            const inp = document.createElement("input");
            inp.type = "text"; inp.placeholder = "搜索画师...";
            inp.style.cssText = "flex:1;padding:4px 8px;border-radius:3px;border:1px solid #0f3460;background:#16213e;color:#e0e0e0;font-size:12px;outline:none;";
            inp.onkeydown = (e) => { if (e.key === "Enter") { artistPage = 1; loadArtists(); } };

            const sBtn = document.createElement("button");
            sBtn.textContent = "🔍"; sBtn.style.cssText = "padding:4px 10px;border-radius:3px;border:none;background:#e94560;color:#fff;cursor:pointer;font-size:14px;";
            sBtn.onclick = () => { artistPage = 1; loadArtists(); };
            topBar.append(inp, sBtn);

            // 画师网格
            const artistGrid = document.createElement("div");
            artistGrid.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;padding:6px;overflow-y:auto;max-height:280px;align-content:flex-start;";

            // 画师翻页
            const artistPageBar = document.createElement("div");
            artistPageBar.style.cssText = "display:none;justify-content:center;gap:6px;padding:4px;font-size:10px;color:#888;flex-shrink:0;";

            topPanel.append(topBar, artistGrid, artistPageBar);
            root.appendChild(topPanel);

            // ═══════════════════════════════════════════
            //  下半：D站画廊
            // ═══════════════════════════════════════════

            const bottomPanel = document.createElement("div");
            bottomPanel.style.cssText = "flex:1;display:flex;flex-direction:column;min-height:0;";

            const bottomBar = document.createElement("div");
            bottomBar.style.cssText = "display:flex;gap:8px;padding:6px 8px;align-items:center;border-bottom:1px solid #0f3460;flex-shrink:0;";
            bottomBar.innerHTML = '<span style="color:#4fc3f7;font-weight:bold;font-size:13px;">📋 D站画廊</span>';

            const dstatus = document.createElement("span");
            dstatus.style.cssText = "color:#888;font-size:11px;flex:1;";
            dstatus.textContent = "← 先在上方选一位画师";
            bottomBar.appendChild(dstatus);

            const postGrid = document.createElement("div");
            postGrid.style.cssText = "flex:1;overflow-y:auto;padding:6px;display:flex;flex-wrap:wrap;gap:4px;align-content:flex-start;min-height:0;";

            const postPageBar = document.createElement("div");
            postPageBar.style.cssText = "display:none;justify-content:center;gap:6px;padding:4px;font-size:10px;color:#888;flex-shrink:0;";

            // 选中信息
            const selectedInfo = document.createElement("div");
            selectedInfo.style.cssText = "display:none;padding:6px 8px;background:#0f3460;border-top:1px solid #e94560;flex-shrink:0;font-size:11px;color:#b0bec5;";

            bottomPanel.append(bottomBar, postGrid, postPageBar, selectedInfo);
            root.appendChild(bottomPanel);

            // ═══════════════════════════════════════════
            //  函数
            // ═══════════════════════════════════════════

            function renderArtistPageBar(total) {
                artistTotal = total;
                const pages = Math.ceil(total / 36);
                if (pages <= 1) { artistPageBar.style.display = "none"; return; }
                artistPageBar.style.display = "flex";
                artistPageBar.innerHTML = "";
                const mk = (t, fn) => { const s=document.createElement("span");s.textContent=t;s.style.cssText="cursor:pointer;color:#4fc3f7;";s.onclick=fn;artistPageBar.appendChild(s); };
                if (artistPage > 1) mk("◀", () => { artistPage--; loadArtists(); });
                for (let i=Math.max(1,artistPage-2); i<=Math.min(pages,artistPage+2); i++) {
                    const sp = document.createElement("span");
                    sp.textContent = i;
                    sp.style.cssText = `cursor:pointer;padding:1px 5px;border-radius:2px;background:${i===artistPage?"#e94560":"transparent"};color:${i===artistPage?"#fff":"#aaa"};`;
                    if (i !== artistPage) sp.onclick = () => { artistPage = i; loadArtists(); };
                    artistPageBar.appendChild(sp);
                }
                if (artistPage < pages) mk("▶", () => { artistPage++; loadArtists(); });
            }

            async function loadArtists() {
                artistGrid.innerHTML = '<div style="padding:30px;color:#888;width:100%;text-align:center;">⏳</div>';
                try {
                    const q = inp.value.trim();
                    const r = await fetch("/mooshie/search", {
                        method:"POST", headers:{"Content-Type":"application/json"},
                        body: JSON.stringify({mode:"artists", query:q, page:artistPage, sort:sortMode}),
                    });
                    const d = await r.json();
                    artists = d.results || [];
                    renderArtistPageBar(d.total || 0);
                } catch { artists = []; }
                renderArtists();
            }

            function renderArtists() {
                artistGrid.innerHTML = "";
                if (!artists.length) {
                    artistGrid.innerHTML = '<div style="padding:40px;color:#888;width:100%;text-align:center;">🔍 搜索 Mooshie 画师（42k+）</div>';
                    return;
                }
                for (const a of artists) {
                    const card = document.createElement("div");
                    const selMark = selectedArtist === a.slug ? "2px solid #e94560" : "1px solid #0f3460";
                    card.style.cssText = `width:calc(12.5% - 4px);background:#16213e;border-radius:3px;overflow:hidden;cursor:pointer;border:${selMark};box-sizing:border-box;flex-shrink:0;`;
                    card.onclick = () => {
                        selectedArtist = a.slug;
                        if (tagW) tagW.value = "@" + (a.trigger || a.name);
                        node.isChanged = true;
                        renderArtists();
                        dstatus.textContent = "⏳ 搜索 @" + (a.trigger||a.name) + " 的作品...";
                        loadDanbooru(a.slug, 1);
                    };

                    const imgDiv = document.createElement("div");
                    imgDiv.style.cssText = "width:100%;aspect-ratio:1;background:#0d0d1a;display:flex;align-items:center;justify-content:center;";
                    if (a.thumb_url) {
                        const img = new Image();
                        img.style.cssText = "width:100%;height:100%;object-fit:cover;";
                        img.src = "/mooshie/image?url=" + encodeURIComponent(a.thumb_url);
                        img.onerror = function() { this.style.display="none"; this.parentElement.textContent="🖼"; this.parentElement.style.fontSize="20px"; this.parentElement.style.color="#444"; };
                        imgDiv.appendChild(img);
                    } else { imgDiv.textContent = "🖼"; imgDiv.style.cssText += "font-size:20px;color:#444;"; }
                    card.appendChild(imgDiv);

                    const nm = document.createElement("div");
                    nm.textContent = a.name || a.trigger || "";
                    nm.style.cssText = "padding:2px 4px;font-size:9px;color:#aaa;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
                    card.appendChild(nm);

                    artistGrid.appendChild(card);
                }
            }

            // ── D站 ──

            let dpage = 1, dtag = "";

            async function loadDanbooru(tag, page) {
                dtag = tag; dpage = page;
                postGrid.innerHTML = '<div style="padding:30px;color:#888;width:100%;text-align:center;">⏳ 加载 D站作品...</div>';
                postPageBar.style.display = "none";
                try {
                    const r = await fetch("/mooshie/danbooru/search", {
                        method:"POST", headers:{"Content-Type":"application/json"},
                        body: JSON.stringify({tag, page}),
                    });
                    const d = await r.json();
                    posts = d.posts || [];
                    dstatus.textContent = `@${tag}: ${posts.length} 张作品`;
                } catch { posts = []; dstatus.textContent = "D站请求失败"; }
                renderPosts();
            }

            function renderPosts() {
                postGrid.innerHTML = "";
                if (!posts.length) {
                    postGrid.innerHTML = '<div style="padding:40px;color:#666;width:100%;text-align:center;">📭 该画师暂无作品 或 搜索失败</div>';
                    return;
                }
                for (const p of posts) {
                    const card = document.createElement("div");
                    const selMark = selectedPost === p.id ? "2px solid #e94560" : "1px solid #0f3460";
                    card.style.cssText = `width:calc(25% - 4px);background:#0f3460;border-radius:4px;overflow:hidden;cursor:pointer;border:${selMark};box-sizing:border-box;flex-shrink:0;`;
                    card.onclick = () => { selectPost(p); };

                    const imgDiv = document.createElement("div");
                    imgDiv.style.cssText = "width:100%;aspect-ratio:1;background:#0d0d1a;display:flex;align-items:center;justify-content:center;";
                    if (p.preview_url) {
                        const img = new Image();
                        img.style.cssText = "width:100%;height:100%;object-fit:cover;";
                        img.src = "/mooshie/image?url=" + encodeURIComponent(p.preview_url);
                        img.onerror = function() { this.style.display="none"; this.parentElement.textContent="🖼"; this.parentElement.style.fontSize="24px"; this.parentElement.style.color="#444"; };
                        imgDiv.appendChild(img);
                    } else { imgDiv.textContent = "🖼"; imgDiv.style.cssText += "font-size:24px;color:#444;"; }
                    card.appendChild(imgDiv);

                    const info = document.createElement("div");
                    info.style.cssText = "padding:2px 4px;font-size:9px;color:#aaa;";
                    const r = p.rating==="e"?"🔞":p.rating==="q"?"⚠️":"";
                    info.textContent = `${r} 👍${p.score||0} ${p.image_width||0}×${p.image_height||0}`;
                    card.appendChild(info);

                    postGrid.appendChild(card);
                }
                // 翻页
                postPageBar.style.display = "flex";
                postPageBar.innerHTML = "";
                if (dpage > 1) {
                    const prev = document.createElement("span");
                    prev.textContent = "◀"; prev.style.cssText = "cursor:pointer;color:#4fc3f7;"; prev.onclick = () => loadDanbooru(dtag, dpage-1);
                    postPageBar.appendChild(prev);
                }
                const pi = document.createElement("span");
                pi.textContent = `第 ${dpage} 页`; pi.style.cssText = "color:#888;";
                postPageBar.appendChild(pi);
                const next = document.createElement("span");
                next.textContent = "▶"; next.style.cssText = "cursor:pointer;color:#4fc3f7;"; next.onclick = () => loadDanbooru(dtag, dpage+1);
                postPageBar.appendChild(next);
            }

            function selectPost(p) {
                selectedPost = p.id;
                if (selW) selW.value = JSON.stringify({post_id: p.id});
                node.isChanged = true;
                renderPosts();

                // 显示选中信息
                selectedInfo.style.display = "block";
                selectedInfo.innerHTML = `
                    <b style="color:#e94560;">✅ 已选 D站 #${p.id}</b>
                    <div style="margin-top:3px;display:grid;grid-template-columns:auto 1fr;gap:2px 8px;">
                        <span style="color:#888;">画师:</span><span>${esc(p.tag_string_artist || "—")}</span>
                        <span style="color:#888;">角色:</span><span>${esc(p.tag_string_character || "—")}</span>
                        <span style="color:#888;">常规:</span><span>${esc((p.tag_string_general || "").slice(0, 120))}</span>
                        <span style="color:#888;">系列:</span><span>${esc(p.tag_string_copyright || "—")}</span>
                        <span style="color:#888;">元标签:</span><span>${esc(p.tag_string_meta || "—")}</span>
                    </div>`;
            }

            function esc(s) { return String(s).replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

            // ── init ──
            this.addDOMWidget("mooshie_ui", "div", root, { onDraw: () => {} });
            loadArtists();
        };
    },
});
