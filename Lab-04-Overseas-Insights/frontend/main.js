/* 出海市场洞察日报 · 前端渲染 + 优雅增强（目录 / 滚动高亮 / 表格 / 锚点） */

function setStatus(message, type = "info") {
  const status = document.getElementById("status");
  if (!status) return;
  if (!message) {
    status.hidden = true;
    status.textContent = "";
    status.dataset.type = "";
    return;
  }
  status.hidden = false;
  status.textContent = message;
  status.dataset.type = type;
}

async function fetchText(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
  return await res.text();
}

function parseMarkdown(markdown) {
  const marked = globalThis.marked;
  if (!marked) throw new Error("Markdown 解析器 marked 未加载。");
  const options = { gfm: true, breaks: false, headerIds: false, mangle: false };
  return typeof marked.parse === "function"
    ? marked.parse(markdown, options)
    : marked(markdown, options);
}

function sanitize(html) {
  const purifier = globalThis.DOMPurify;
  if (!purifier) throw new Error("HTML 清洗器 DOMPurify 未加载。");
  return purifier.sanitize(html, { USE_PROFILES: { html: true } });
}

function slugify(text, used) {
  let base = (text || "section")
    .trim()
    .toLowerCase()
    .replace(/[\s·／/]+/g, "-")
    .replace(/[^\w一-龥-]/g, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  if (!base) base = "section";
  let slug = base;
  let i = 2;
  while (used.has(slug)) slug = `${base}-${i++}`;
  used.add(slug);
  return slug;
}

/* Pull the report's H1 + leading meta into the hero; remove from body. */
function hydrateHero(content) {
  const h1 = content.querySelector("h1");
  if (h1) {
    const title = h1.textContent.trim();
    if (title) {
      document.getElementById("hero-title").textContent = title;
      document.title = title;
    }
  }

  // Collect leading meta lines (date / category / market) before the first H2.
  const metaText = [];
  let node = h1 ? h1.nextElementSibling : content.firstElementChild;
  const toRemove = [];
  while (node && node.tagName !== "H2") {
    const next = node.nextElementSibling;
    if (/^(P|UL|OL|BLOCKQUOTE|HR)$/.test(node.tagName)) {
      const t = node.textContent.replace(/\s+/g, " ").trim();
      if (t) metaText.push(t);
      toRemove.push(node);
    }
    node = next;
  }
  if (h1) h1.remove();

  const blob = metaText.join(" ｜ ");
  const dateMatch = blob.match(/(20\d{2}[-年./]\d{1,2}[-月./]\d{1,2}日?)/);
  if (dateMatch) {
    const d = dateMatch[1];
    const el1 = document.getElementById("topbar-date");
    const el2 = document.getElementById("footer-updated");
    if (el1) el1.textContent = `📅 ${d}`;
    if (el2) el2.textContent = `更新于 ${d}`;
  }
  if (blob) {
    const sub = document.getElementById("hero-sub");
    if (sub) sub.textContent = blob.length > 160 ? blob.slice(0, 159) + "…" : blob;
  }
  // Remove the meta nodes we lifted into the hero to avoid duplication.
  toRemove.forEach((n) => n.remove());
}

/* Wrap tables for horizontal scroll on small screens. */
function wrapTables(content) {
  content.querySelectorAll("table").forEach((table) => {
    if (table.parentElement && table.parentElement.classList.contains("table-wrap")) return;
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    table.parentNode.insertBefore(wrap, table);
    wrap.appendChild(table);
  });
}

/* Build the sticky TOC from H2 headings + add hover anchors. */
function buildToc(content) {
  const used = new Set();
  const headings = [...content.querySelectorAll("h2")];
  const tocList = document.getElementById("toc-list");
  const toc = document.getElementById("toc");
  if (!headings.length || !tocList || !toc) return [];

  const items = headings.map((h) => {
    const id = slugify(h.textContent, used);
    h.id = id;
    const a = document.createElement("a");
    a.className = "anchor";
    a.href = `#${id}`;
    a.textContent = "#";
    a.setAttribute("aria-hidden", "true");
    h.appendChild(a);

    const li = document.createElement("li");
    li.className = "toc__item";
    const link = document.createElement("a");
    link.href = `#${id}`;
    link.textContent = h.textContent.replace(/#$/, "").trim();
    li.appendChild(link);
    tocList.appendChild(li);
    return { id, heading: h, link };
  });

  // Also id the H3s for deep links (no TOC entry, keeps it clean).
  content.querySelectorAll("h3").forEach((h) => { if (!h.id) h.id = slugify(h.textContent, used); });

  toc.hidden = false;
  return items;
}

/* Scroll-spy: highlight the section currently in view. */
function wireScrollSpy(items) {
  if (!items.length || !("IntersectionObserver" in window)) return;
  const byId = new Map(items.map((it) => [it.id, it.link]));
  let activeId = null;
  const setActive = (id) => {
    if (id === activeId) return;
    activeId = id;
    items.forEach((it) => it.link.classList.toggle("is-active", it.id === id));
  };

  const visible = new Map();
  const obs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) visible.set(e.target.id, e.intersectionRatio);
        else visible.delete(e.target.id);
      });
      if (visible.size) {
        const top = [...visible.entries()].sort((a, b) => b[1] - a[1])[0][0];
        setActive(top);
      } else {
        // fallback: nearest heading above the fold
        const above = items.filter((it) => it.heading.getBoundingClientRect().top < 120);
        if (above.length) setActive(above[above.length - 1].id);
      }
    },
    { rootMargin: "-80px 0px -65% 0px", threshold: [0, 0.25, 0.5, 1] }
  );
  items.forEach((it) => obs.observe(it.heading));
  if (byId.size) setActive(items[0].id);
}

async function loadReport(reportPath) {
  const content = document.getElementById("content");
  try {
    const markdown = await fetchText(reportPath);
    content.innerHTML = sanitize(parseMarkdown(markdown));
    hydrateHero(content);
    wrapTables(content);
    const items = buildToc(content);
    wireScrollSpy(items);
    setStatus(null);
    if (location.hash) {
      const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (el) el.scrollIntoView();
    }
  } catch (err) {
    console.error(err);
    content.innerHTML = "";
    setStatus(`报告加载失败（${reportPath}）：${err?.message || err}`, "error");
  }
}

loadReport("report.md");
