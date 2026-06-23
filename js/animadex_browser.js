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

            const tagW = node.widgets?.find(w => w.name === "_tag");
            if (tagW) { tagW.computeSize = () => [0.1, 20]; tagW.serialize = true; }
            const selW = node.widgets?.find(w => w.name === "selection_data");
            if (selW) { selW.computeSize = () => [0.1, 20]; selW.serialize = true; }

            // ── state ──
            let sortMode = "count", artists = [], artistPage = 1, artistTotal = 0;
            let posts = [], selectedPost = null, selectedArtist = null;
            let favorites = [], showFavorites = false;
            let dpage = 1, dtag = "";

            const root = document.createElement("div");
            root.style.cssText = "width:100%;height:100%;display:flex;flex-direction:column;background:#1a1a1a;border-radius:6px;min-height:0;";

            // ═══════════════ 上半：画师浏览 ═══════════════
            const topPanel = document.createElement("div");
            topPanel.style.cssText = "flex:0 0 auto;display:flex;flex-direction:column;border-bottom:2px solid #e94560;";

            const topBar = document.createElement("div");
            topBar.style.cssText = "display:flex;gap:6px;padding:8px;align-items:center;border-bottom:1px solid #222;flex-shrink:0;";
            const topLabel = document.createElement("span");
            topLabel.textContent = "🎨 画师浏览"; topLabel.style.cssText = "color:#e94560;font-weight:bold;font-size:13px;flex-shrink:0;";

            const sortBtns = {};
            for (const [sk, sl] of [["count","🔥"],["fav_count","❤️"],["random","🔀"]]) {
                const sb = document.createElement("button");
                sb.textContent = sl; sb.title = sk==="count"?"热门":sk==="fav_count"?"最多喜欢":"随机";
                sb.style.cssText = `padding:3px 6px;border-radius:3px;border:none;cursor:pointer;font-size:11px;background:${sk===sortMode?"#e94560":"#2a2a3a"};color:${sk===sortMode?"#fff":"#888"};`;
                sb.onclick = () => { sortMode = sk; artistPage = 1; for (const [k,v] of Object.entries(sortBtns)) { v.style.background=k===sortMode?"#e94560":"#2a2a3a"; v.style.color=k===sortMode?"#fff":"#888"; } loadArtists(); };
                sortBtns[sk] = sb; topBar.appendChild(sb);
            }

            const inp = document.createElement("input");
            inp.type = "text"; inp.placeholder = "搜索画师...";
            inp.style.cssText = "flex:1;padding:4px 8px;border-radius:3px;border:1px solid #222;background:#16213e;color:#e0e0e0;font-size:12px;outline:none;";
            inp.onkeydown = (e) => { if (e.key === "Enter") { artistPage = 1; loadArtists(); } };
            const sBtn = document.createElement("button");
            sBtn.textContent = "🔍"; sBtn.style.cssText = "padding:4px 10px;border-radius:3px;border:none;background:#e94560;color:#fff;cursor:pointer;font-size:14px;";
            sBtn.onclick = () => { artistPage = 1; loadArtists(); };
            topBar.append(topLabel, inp, sBtn);

            const artistGrid = document.createElement("div");
            artistGrid.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;padding:6px;overflow-y:auto;max-height:260px;align-content:flex-start;";
            const artistPageBar = document.createElement("div");
            artistPageBar.style.cssText = "display:none;justify-content:center;gap:6px;padding:4px;font-size:10px;color:#888;flex-shrink:0;";
            topPanel.append(topBar, artistGrid, artistPageBar);
            root.appendChild(topPanel);

            // ═══════════════ 下半：D站画廊 ═══════════════
            const bottomPanel = document.createElement("div");
            bottomPanel.style.cssText = "flex:1;display:flex;flex-direction:column;min-height:0;";

            const bottomBar = document.createElement("div");
            bottomBar.style.cssText = "display:flex;gap:6px;padding:6px 8px;align-items:center;border-bottom:1px solid #222;flex-shrink:0;";
            const dLabel = document.createElement("span");
            dLabel.textContent = "📋 D站"; dLabel.style.cssText = "color:#00c9a7;font-weight:bold;font-size:12px;flex-shrink:0;";

            const dInp = document.createElement("input");
            dInp.type = "text"; dInp.placeholder = "搜索 D站 (tag/画师/作品名)...";
            dInp.style.cssText = "flex:1;padding:4px 8px;border-radius:3px;border:1px solid #222;background:#16213e;color:#e0e0e0;font-size:12px;outline:none;";
            dInp.onkeydown = (e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); const first = acList.querySelector("div"); if (first) { first.focus(); first.style.background = "#0d2137"; } return; }
                if (e.key === "Enter") { if (acList.style.display !== "none") { acList.style.display = "none"; return; } showFavorites = false; dpage = 1; loadDanbooru(dInp.value.trim(), 1); }
            };

            // 自动补全下拉
            const acList = document.createElement("div");
            acList.style.cssText = "display:none;position:absolute;top:100%;left:0;right:0;background:#1a1a1a;border:1px solid #222;border-radius:0 0 4px 4px;max-height:240px;overflow-y:auto;z-index:999;";
            let _acTimer = null;
            bottomBar.style.position = "relative";

            dInp.oninput = () => {
                const q = dInp.value.trim();
                if (!q || q.length < 1) { acList.style.display = "none"; return; }
                clearTimeout(_acTimer);
                _acTimer = setTimeout(async () => {
                    try {
                        const r = await fetch("/mooshie/fuzzy_tags", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({query: q}) });
                        const d = await r.json();
                        const tags = d.tags || [];
                        acList.innerHTML = "";
                        if (!tags.length) { acList.style.display = "none"; return; }
                        for (const t of tags) {
                            const row = document.createElement("div");
                            row.style.cssText = "padding:5px 8px;cursor:pointer;color:#b0bec5;font-size:12px;border-bottom:1px solid #222;display:flex;gap:6px;";
                            row.onmouseover = () => row.style.background = "#0d2137";
                            row.onmouseout = () => row.style.background = "transparent";
                            row.onclick = () => { dInp.value = t.tag; acList.style.display = "none"; dpage=1; loadDanbooru(t.tag, 1); };
                            row.innerHTML = `<span style="font-weight:bold;color:#e0e0e0;">${t.tag}</span><span style="color:#888;margin-left:auto;">${t.cn||""}</span>`;
                            acList.appendChild(row);
                        }
                        acList.style.display = "block";
                    } catch { acList.style.display = "none"; }
                }, 200);
            };
            dInp.onblur = () => setTimeout(() => acList.style.display = "none", 200);
            bottomBar.appendChild(acList);

            const dBtn = document.createElement("button");
            dBtn.textContent = "🔍"; dBtn.style.cssText = "padding:4px 10px;border-radius:3px;border:none;background:#222;color:#00c9a7;cursor:pointer;font-size:13px;";
            dBtn.onclick = () => { showFavorites = false; dpage = 1; loadDanbooru(dInp.value.trim(), 1); };

            // 分级按钮 S/Q/E
            let ratingFilter = null; // null=全部, "s"/"q"/"e" 或组合
            const ratingBtns = {};
            for (const [rk, rl, rc] of [["s","S","#4caf50"],["q","Q","#ff9800"],["e","E","#e94560"]]) {
                const rb = document.createElement("button");
                rb.textContent = rl;
                rb.title = rk==="s"?"安全":rk==="q"?"可疑":"R18";
                rb.style.cssText = `padding:3px 7px;border-radius:3px;border:none;cursor:pointer;font-size:11px;background:transparent;color:#666;`;
                rb.onclick = () => {
                    if (ratingFilter === rk) { ratingFilter = null; }
                    else { ratingFilter = rk; }
                    for (const [k, v] of Object.entries(ratingBtns)) {
                        v.style.background = ratingFilter === k ? rc : "transparent";
                        v.style.color = ratingFilter === k ? "#fff" : "#666";
                    }
                    dpage = 1; loadDanbooru(dInp.value.trim(), 1);
                };
                ratingBtns[rk] = rb;
                bottomBar.appendChild(rb);
            }

            const favTab = document.createElement("button");
            favTab.textContent = "⭐ 收藏"; favTab.style.cssText = "padding:4px 8px;border-radius:3px;border:none;background:transparent;color:#888;cursor:pointer;font-size:11px;";
            favTab.onclick = () => {
                showFavorites = !showFavorites;
                favTab.style.background = showFavorites ? "#e94560" : "transparent";
                favTab.style.color = showFavorites ? "#fff" : "#888";
                if (showFavorites) { loadFavorites(); } else { renderPosts(); }
            };

            bottomBar.append(dLabel, dInp, dBtn, favTab);

            const postGrid = document.createElement("div");
            postGrid.style.cssText = "flex:1;overflow-y:auto;padding:6px;columns:3;column-gap:4px;min-height:0;";
            const postPageBar = document.createElement("div");
            postPageBar.style.cssText = "display:none;justify-content:center;gap:6px;padding:4px;font-size:10px;color:#888;flex-shrink:0;";

            const selectedInfo = document.createElement("div");
            selectedInfo.style.cssText = "display:none;padding:6px 8px;background:#222;border-top:1px solid #e94560;flex-shrink:0;font-size:11px;color:#b0bec5;";

            bottomPanel.append(bottomBar, postGrid, postPageBar, selectedInfo);
            root.appendChild(bottomPanel);

            // ═══════════════ 画师函数 ═══════════════
            function renderArtistPageBar(total) {
                artistTotal = total;
                const pages = Math.ceil(total / 36);
                if (pages <= 1) { artistPageBar.style.display = "none"; return; }
                artistPageBar.style.display = "flex"; artistPageBar.innerHTML = "";
                const mk = (t, fn) => { const s=document.createElement("span");s.textContent=t;s.style.cssText="cursor:pointer;color:#00c9a7;";s.onclick=fn;artistPageBar.appendChild(s); };
                if (artistPage > 1) mk("◀", () => { artistPage--; loadArtists(); });
                for (let i=Math.max(1,artistPage-2); i<=Math.min(pages,artistPage+2); i++) {
                    const sp = document.createElement("span"); sp.textContent = i;
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
                    const r = await fetch("/mooshie/search", { method:"POST", headers:{"Content-Type":"application/json"},
                        body: JSON.stringify({mode:"artists", query:q, page:artistPage, sort:sortMode}) });
                    const d = await r.json(); artists = d.results || []; renderArtistPageBar(d.total || 0);
                } catch { artists = []; }
                renderArtists();
            }

            function renderArtists() {
                artistGrid.innerHTML = "";
                if (!artists.length) { artistGrid.innerHTML = '<div style="padding:40px;color:#888;width:100%;text-align:center;">🔍 搜索 Mooshie 画师（42k+）</div>'; return; }
                for (const a of artists) {
                    const card = document.createElement("div");
                    card.style.cssText = `width:calc(12.5% - 4px);background:#16213e;border-radius:3px;overflow:hidden;cursor:pointer;border:${selectedArtist===a.slug?"2px solid #e94560":"1px solid #222"};box-sizing:border-box;flex-shrink:0;`;
                    card.onclick = () => {
                        selectedArtist = a.slug; if (tagW) tagW.value = "@" + (a.trigger || a.name); node.isChanged = true;
                        renderArtists(); dInp.value = a.slug || a.trigger || "";
                    };
                    const imgDiv = document.createElement("div");
                    imgDiv.style.cssText = "width:100%;aspect-ratio:1;background:#0d0d1a;display:flex;align-items:center;justify-content:center;";
                    if (a.thumb_url) {
                        const img = new Image(); img.style.cssText = "width:100%;height:100%;object-fit:cover;";
                        img.src = "/mooshie/image?url=" + encodeURIComponent(a.thumb_url);
                        img.onerror = function() { this.style.display="none"; this.parentElement.textContent="🖼"; this.parentElement.style.fontSize="20px"; this.parentElement.style.color="#444"; };
                        imgDiv.appendChild(img);
                    } else { imgDiv.textContent = "🖼"; imgDiv.style.cssText += "font-size:20px;color:#444;"; }
                    card.appendChild(imgDiv);
                    const nm = document.createElement("div"); nm.textContent = a.name || a.trigger || "";
                    nm.style.cssText = "padding:2px 4px;font-size:9px;color:#aaa;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
                    card.appendChild(nm);
                    artistGrid.appendChild(card);
                }
            }

            // ═══════════════ D站 + 收藏 渲染 ═══════════════
            function esc(s) { return String(s).replace(/</g,"&lt;").replace(/>/g,"&gt;"); }

            async function loadDanbooru(tag, page) {
                dtag = tag; dpage = page; showFavorites = false;
                favTab.style.background = "transparent"; favTab.style.color = "#888";
                postGrid.innerHTML = '<div style="padding:30px;color:#888;width:100%;text-align:center;">⏳</div>';
                postPageBar.style.display = "none";
                try {
                    const r = await fetch("/mooshie/danbooru/search", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({tag, page, rating: ratingFilter}) });
                    const d = await r.json(); posts = d.posts || [];
                    dInp.style.borderColor = posts.length ? "#222" : "#e94560";
                } catch { posts = []; }
                renderPosts();
            }

            async function loadFavorites() {
                postGrid.innerHTML = '<div style="padding:30px;color:#888;width:100%;text-align:center;">⏳</div>';
                postPageBar.style.display = "none";
                try {
                    const r = await fetch("/mooshie/favorites"); const d = await r.json();
                    favorites = d.favorites || [];
                } catch { favorites = []; }
                renderFavs();
            }

            function isFav(postId) { return favorites.some(f => f.id === postId); }

            async function toggleFav(post) {
                const fid = post.id;
                if (isFav(fid)) {
                    await fetch("/mooshie/favorites/remove", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({id: fid}) });
                    favorites = favorites.filter(f => f.id !== fid);
                } else {
                    const fp = { id: post.id, preview_url: post.preview_url, large_url: post.large_url, file_url: post.file_url,
                        tag_string_artist: post.tag_string_artist, tag_string_character: post.tag_string_character,
                        tag_string_general: post.tag_string_general, tag_string_copyright: post.tag_string_copyright,
                        tag_string_meta: post.tag_string_meta, tag_string: post.tag_string,
                        rating: post.rating, score: post.score, image_width: post.image_width, image_height: post.image_height };
                    await fetch("/mooshie/favorites/add", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({post: fp}) });
                    favorites.unshift(fp);
                }
                if (showFavorites) renderFavs(); else renderPosts();
            }

            function renderPosts() {
                postGrid.innerHTML = "";
                if (!posts.length) { postGrid.innerHTML = '<div style="padding:40px;color:#666;width:100%;text-align:center;">📭 无结果</div>'; postPageBar.style.display="none"; return; }
                posts.forEach(p => renderCard(p, p));
                postPageBar.style.display = "flex"; postPageBar.innerHTML = "";
                if (dpage > 1) { const prev=document.createElement("span");prev.textContent="◀";prev.style.cssText="cursor:pointer;color:#00c9a7;";prev.onclick=()=>loadDanbooru(dtag,dpage-1);postPageBar.appendChild(prev); }
                const pi=document.createElement("span");pi.textContent=`第 ${dpage} 页`;pi.style.cssText="color:#888;";postPageBar.appendChild(pi);
                const next=document.createElement("span");next.textContent="▶";next.style.cssText="cursor:pointer;color:#00c9a7;";next.onclick=()=>loadDanbooru(dtag,dpage+1);postPageBar.appendChild(next);
            }

            function renderFavs() {
                postGrid.innerHTML = "";
                if (!favorites.length) { postGrid.innerHTML = '<div style="padding:40px;color:#666;width:100%;text-align:center;">⭐ 暂无收藏，去 D站搜图后点 ❤️</div>'; return; }
                favorites.forEach(p => renderCard(p, p));
            }

            function renderCard(p, postData) {
                const card = document.createElement("div");
                card.style.cssText = `width:100%;background:#222;border-radius:4px;overflow:hidden;cursor:pointer;border:${selectedPost===p.id?"2px solid #e94560":"1px solid #222"};box-sizing:border-box;margin-bottom:4px;break-inside:avoid;position:relative;`;
                card.onclick = () => { if (!showFavorites) selectPost(postData); else selectFav(postData); };

                // 双击大图
                card.ondblclick = (e) => { e.stopPropagation(); showLargeImage(postData); };

                const imgDiv = document.createElement("div");
                imgDiv.style.cssText = "width:100%;background:#0d0d1a;display:flex;align-items:center;justify-content:center;";
                if (p.preview_url) {
                    const img = new Image(); img.style.cssText = "width:100%;height:auto;display:block;";
                    img.src = "/mooshie/image?url=" + encodeURIComponent(p.preview_url);
                    img.onerror = function() { this.style.display="none"; this.parentElement.textContent="🖼"; this.parentElement.style.fontSize="24px"; this.parentElement.style.color="#444"; };
                    imgDiv.appendChild(img);
                } else { imgDiv.textContent = "🖼"; imgDiv.style.cssText += "font-size:24px;color:#444;"; }
                card.appendChild(imgDiv);

                // 底栏信息
                const inf = document.createElement("div");
                inf.style.cssText = "display:flex;justify-content:space-between;align-items:center;padding:2px 4px;font-size:9px;color:#aaa;";
                const r = p.rating==="e"?"🔞":p.rating==="q"?"⚠️?":"";
                inf.innerHTML = `<span>${r} ★${p.score||0}</span><span>${p.image_width||0}×${p.image_height||0}</span>`;
                card.appendChild(inf);

                // 按钮行
                const btns = document.createElement("div");
                btns.style.cssText = "display:flex;gap:2px;padding:2px 4px;";

                // ❤️ 收藏
                const h = document.createElement("button"); h.textContent = isFav(p.id) ? "❤️" : "🤍";
                h.title = isFav(p.id) ? "取消收藏" : "收藏";
                h.style.cssText = "flex:1;padding:2px 0;border:none;border-radius:2px;cursor:pointer;font-size:14px;background:transparent;";
                h.onclick = (e) => { e.stopPropagation(); toggleFav(postData); };
                btns.appendChild(h);

                // 📋 标签
                const t = document.createElement("button"); t.textContent = "📋";
                t.title = "查看分类标签"; t.style.cssText = "flex:1;padding:2px 0;border:none;border-radius:2px;cursor:pointer;font-size:12px;background:transparent;";
                t.onclick = (e) => { e.stopPropagation(); showTagPopup(postData); };
                btns.appendChild(t);

                card.appendChild(btns);
                postGrid.appendChild(card);
            }

            // ═══════════════ 选中帖子 ═══════════════
            function pushToEditablePrompt(post) {
                // 找到图中所有 EditablePrompt 节点，直接往框里填上游值
                const data = {
                    artist: post.tag_string_artist || "",
                    character: post.tag_string_character || "",
                    series: post.tag_string_copyright || "",
                    general: post.tag_string_general || "",
                    meta: post.tag_string_meta || "",
                };
                for (const n of (app.graph._nodes || [])) {
                    if (n.type !== "EditablePrompt") continue;
                    // 写入 upstream_data widget
                    const upW = n.widgets?.find(w => w.name === "upstream_data");
                    if (upW) upW.value = JSON.stringify(data);

                    // 对于每个分类，模式为"跟随"时填入上游值
                    for (const cat of ["artist","character","series","general","meta"]) {
                        const modeW = n.widgets?.find(w => w.name === `mode_${cat}`);
                        if (modeW && modeW.value === "跟随") {
                            const textW = n.widgets?.find(w => w.name === cat);
                            if (textW) {
                                textW.value = data[cat] || "";
                                if (textW.callback) textW.callback(textW.value);
                            }
                        }
                    }
                    n.setDirtyCanvas(true);
                }
            }

            function selectPost(p) {
                selectedPost = p.id;
                if (selW) selW.value = JSON.stringify({post_id: p.id}); node.isChanged = true;
                pushToEditablePrompt(p);
                renderPosts();
                selectedInfo.style.display = "block";
                selectedInfo.innerHTML = `<b style="color:#e94560;">✅ D站 #${p.id}</b>
                    <div style="margin-top:3px;display:grid;grid-template-columns:auto 1fr;gap:2px 8px;">
                        <span style="color:#888;">画师:</span><span>${esc(p.tag_string_artist||"—")}</span>
                        <span style="color:#888;">角色:</span><span>${esc(p.tag_string_character||"—")}</span>
                        <span style="color:#888;">常规:</span><span>${esc((p.tag_string_general||"").slice(0,120))}</span>
                        <span style="color:#888;">系列:</span><span>${esc(p.tag_string_copyright||"—")}</span>
                    </div>`;
            }

            function selectFav(p) {
                selectedPost = p.id;
                if (selW) selW.value = JSON.stringify({post_id: p.id}); node.isChanged = true;
                pushToEditablePrompt(p);
                selectedInfo.style.display = "block";
                selectedInfo.innerHTML = `<b style="color:#e94560;">⭐ 收藏 #${p.id}</b>
                    <div style="margin-top:3px;display:grid;grid-template-columns:auto 1fr;gap:2px 8px;">
                        <span style="color:#888;">画师:</span><span>${esc(p.tag_string_artist||"—")}</span>
                        <span style="color:#888;">角色:</span><span>${esc(p.tag_string_character||"—")}</span>
                        <span style="color:#888;">常规:</span><span>${esc((p.tag_string_general||"").slice(0,120))}</span>
                    </div>`;
            }

            // ═══════════════ 📋 标签弹窗 ═══════════════
            async function showTagPopup(p) {
                const ov = document.createElement("div");
                ov.style.cssText = "position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.5);backdrop-filter:blur(3px);display:flex;align-items:center;justify-content:center;";
                ov.onclick = (e) => { if (e.target === ov) ov.remove(); };
                const box = document.createElement("div");
                box.style.cssText = "background:rgba(26,26,46,0.95);border:1px solid #222;border-radius:10px;padding:16px;max-width:90%;max-height:80%;overflow:auto;color:#e0e0e0;font-size:13px;box-shadow:0 8px 32px rgba(0,0,0,0.5);";
                box.innerHTML = '<div style="text-align:center;color:#888;">⏳ 加载标签...</div>';
                ov.appendChild(box); document.body.appendChild(ov);

                try {
                    const r = await fetch(`/mooshie/post/${p.id}`); const d = await r.json();
                    if (!d.success) { box.innerHTML = '<div style="text-align:center;color:#e94560;">加载失败</div>'; return; }
                    const post = d.post || {};
                    let total = 0;
                    let html = `<div style="font-weight:bold;color:#e94560;font-size:14px;margin-bottom:8px;">📋 D站 #${p.id} · ${d.total_tags || 0} 标签</div>`;
                    const cats = [
                        ["tag_string_meta",      "质量/元", "#ff6b6b"],
                        ["tag_string_artist",    "画师",   "#ff6ec7"],
                        ["tag_string_character", "角色",   "#6bcb77"],
                        ["tag_string_copyright", "系列",   "#4d96ff"],
                        ["tag_string_general",   "常规",   "#a0a0a0"],
                    ];
                    for (const [field, label, color] of cats) {
                        const raw = (post[field] || "").trim();
                        const tags = raw ? raw.split(/\s+/).filter(Boolean) : [];
                        if (!tags.length) continue;
                        total += tags.length;
                        html += `<div style="margin:6px 0;"><span style="background:${color}22;color:${color};padding:1px 6px;border-radius:3px;font-size:11px;font-weight:bold;">${label}</span> `;
                        for (const tg of tags) {
                            html += `<span class="ms-tag" data-tag="${esc(tg)}" style="cursor:pointer;display:inline-block;margin:2px 4px;color:#b0bec5;" title="搜索 '${esc(tg)}'">${esc(tg)}</span>`;
                        }
                        html += `</div>`;
                    }
                    html += `<div style="text-align:center;margin-top:10px;color:#888;font-size:11px;">🖱️ 点击 tag 搜索 | ✕ 点击外部关闭</div>`;
                    box.innerHTML = html;

                    box.querySelectorAll(".ms-tag").forEach(el => {
                        el.onclick = () => {
                            dInp.value = el.dataset.tag; ov.remove();
                            showFavorites = false; favTab.style.background="transparent"; favTab.style.color="#888";
                            dpage = 1; loadDanbooru(el.dataset.tag, 1);
                        };
                    });
                } catch { box.innerHTML = '<div style="text-align:center;color:#e94560;">网络错误</div>'; }
            }

            // ═══════════════ 🖼️ 双击大图 ═══════════════
            function showLargeImage(p) {
                const ov = document.createElement("div");
                ov.style.cssText = "position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.88);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:12px;";
                let img = document.createElement("img");
                img.style.cssText = "max-width:95%;max-height:80%;object-fit:contain;border-radius:6px;box-shadow:0 4px 30px rgba(0,0,0,0.6);cursor:zoom-out;";
                const sUrl = p.large_url || p.preview_url || "";
                if (sUrl) img.src = "/mooshie/image?url=" + encodeURIComponent(sUrl);
                img.onclick = () => ov.remove();
                img.onerror = () => { if (p.preview_url && img.src !== "/mooshie/image?url="+encodeURIComponent(p.preview_url)) img.src = "/mooshie/image?url="+encodeURIComponent(p.preview_url); };
                ov.appendChild(img);

                const bar = document.createElement("div");
                bar.style.cssText = "display:flex;gap:10px;align-items:center;";
                const origBtn = document.createElement("span");
                origBtn.textContent = "📥 查看原图"; origBtn.style.cssText = "padding:8px 18px;border-radius:6px;background:#222;color:#00c9a7;cursor:pointer;font-size:14px;font-weight:bold;";
                let showingOrig = false;
                origBtn.onclick = () => {
                    if (showingOrig) return; showingOrig = true;
                    origBtn.textContent = "⏳ 加载中..."; origBtn.style.opacity = "0.5";
                    const oUrl = p.file_url || p.large_url || "";
                    const test = new Image();
                    test.onload = () => { img.src = "/mooshie/image?url="+encodeURIComponent(oUrl); origBtn.textContent="✅ 原图"; origBtn.style.opacity="1"; };
                    test.onerror = () => { origBtn.textContent="❌ 加载失败"; origBtn.style.opacity="1"; showingOrig = false; };
                    test.src = "/mooshie/image?url="+encodeURIComponent(oUrl);
                };
                const dlBtn = document.createElement("span");
                dlBtn.textContent = "⏬ 下载"; dlBtn.style.cssText = "padding:8px 18px;border-radius:6px;background:#e94560;color:#fff;cursor:pointer;font-size:14px;font-weight:bold;";
                dlBtn.onclick = async () => {
                    try { const r=await fetch("/mooshie/image?url="+encodeURIComponent(sUrl)); const b=await r.blob();
                        const a=document.createElement("a"); a.href=URL.createObjectURL(b); a.download=p.id+"_"+sUrl.split("/").pop(); a.click(); }
                    catch(ex) { alert("下载失败"); }
                };
                const closeBtn = document.createElement("span");
                closeBtn.textContent = "✕ 关闭"; closeBtn.style.cssText = "padding:8px 18px;border-radius:6px;background:#2a2a3a;color:#aaa;cursor:pointer;font-size:14px;";
                closeBtn.onclick = () => ov.remove();
                bar.append(origBtn, dlBtn, closeBtn);
                ov.appendChild(bar);
                document.body.appendChild(ov);
            }

            // ═══════════════ init ═══════════════
            this.addDOMWidget("mooshie_ui", "div", root, { onDraw: () => {} });
            loadArtists();
        };
    },
});
