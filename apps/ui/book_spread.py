"""Two-page PDF spread for Official Pottermore preview (display-only).

Served from the UI :8502 companion. Streams allowlisted publisher PDFs through
our host so the browser can render them (Pottermore sets X-Frame-Options).
Bytes are never written to SQLite / FTS (ADR-008 metadata-only).

Includes:
- pdf.js canvas pages + **TextLayer** (Speak Screen / selection)
- **Reading panel** with extracted Ukrainian text for Listen to Page
- Lightweight CSS 3D page peel (turn.js-inspired, no jQuery)
"""

from __future__ import annotations

import html
import json

from apps.ui.view_model import (
    POTTERMORE_FIXTURE_PATH,
    OfficialPreviewBook,
    load_official_preview_books,
)


def official_book_by_id(book_id: str) -> OfficialPreviewBook | None:
    for book in load_official_preview_books("uk", fixture_path=POTTERMORE_FIXTURE_PATH):
        if book.id == book_id:
            return book
    return None


def build_book_spread_html(book: OfficialPreviewBook) -> str:
    """Full HTML: open book + text layer + Listen/Reading panel."""
    title = html.escape(book.title)
    authors = html.escape(", ".join(book.authors))
    book_id_js = json.dumps(book.id)
    title_js = json.dumps(book.title)
    return f"""<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — MagicLib</title>
  <link rel="stylesheet"
    href="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.8.69/pdf_viewer.min.css">
  <style>
    :root {{
      --shell: #120e0a; --panel: #fffaf0; --gold: #e2b85f; --gold-dim: #8a5b13;
      --candle: #d4893a; --teal: #4fd1c5; --ink: #241c16;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; color: #fffaf0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(ellipse 70% 45% at 50% -5%,
          color-mix(in srgb, var(--gold) 22%, transparent), transparent 60%),
        radial-gradient(circle at 15% 80%,
          color-mix(in srgb, var(--candle) 28%, transparent), transparent 32%),
        linear-gradient(180deg, #1c1610 0%, var(--shell) 55%, #080604 100%);
    }}
    header {{
      display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center;
      justify-content: space-between; padding: 0.75rem 1rem;
      background: color-mix(in srgb, #000 40%, transparent);
      border-bottom: 1px solid color-mix(in srgb, var(--gold) 35%, transparent);
    }}
    header h1 {{ margin: 0; font-size: clamp(1rem, 2.5vw, 1.35rem); font-weight: 500; }}
    header .by {{ color: #d4c4a8; font-size: 0.9rem; }}
    .tools {{ display: flex; flex-wrap: wrap; gap: 0.5rem; align-items: center; }}
    button {{
      font: 500 1rem system-ui, sans-serif; min-height: 44px; padding: 0.5rem 1rem;
      border-radius: 8px; cursor: pointer; border: 1px solid var(--gold-dim);
      background: var(--gold-dim); color: #fffaf0;
      box-shadow: 0 0 14px color-mix(in srgb, var(--gold) 22%, transparent);
    }}
    button.ghost {{ background: transparent; color: #fffaf0; }}
    button.active {{ background: var(--gold); color: #1a140c; border-color: var(--gold); }}
    button:disabled {{ opacity: 0.4; cursor: not-allowed; box-shadow: none; }}
    .status {{
      font: 0.9rem system-ui, sans-serif; color: #d4c4a8; min-width: 9rem; text-align: center;
    }}
    .stage-wrap {{ padding: 1rem; max-width: 1100px; margin: 0 auto; }}
    .book {{
      position: relative; aspect-ratio: 16/9; width: 100%; border-radius: 14px;
      overflow: hidden; perspective: 2200px;
      background: linear-gradient(90deg, #1a1510 0%, #2a2218 46%,
        color-mix(in srgb, var(--gold) 70%, #fff) 50%, #2a2218 54%, #1a1510 100%);
      box-shadow: 0 28px 70px #000c, 0 0 50px color-mix(in srgb, var(--gold) 22%, transparent);
    }}
    .book::after {{
      content: ""; position: absolute; left: 50%; top: 6%; bottom: 6%; width: 3px; z-index: 4;
      transform: translateX(-50%); pointer-events: none;
      background: linear-gradient(180deg, transparent, var(--gold), transparent);
      box-shadow: 0 0 18px var(--gold); animation: hl-spine 3.2s ease-in-out infinite;
    }}
    .spread {{
      display: grid; grid-template-columns: 1fr 1fr; height: 100%;
      position: relative; z-index: 1;
    }}
    .page {{
      position: relative; background: var(--panel); display: flex; align-items: center;
      justify-content: center; overflow: hidden;
    }}
    .page.left {{ box-shadow: inset -22px 0 36px #0003; }}
    .page.right {{ box-shadow: inset 22px 0 36px #0003; }}
    .page-stack {{ position: relative; max-width: 100%; max-height: 100%; }}
    .page-stack canvas {{ display: block; max-width: 100%; max-height: 100%; }}
    .textLayer {{
      position: absolute; inset: 0; z-index: 2; opacity: 0.28; line-height: 1;
      overflow: hidden; transform-origin: 0 0; pointer-events: auto;
    }}
    .textLayer span {{ color: transparent; position: absolute; white-space: pre; cursor: text; }}
    .flip-leaf {{
      position: absolute; top: 0; bottom: 0; width: 50%; z-index: 5;
      transform-style: preserve-3d; pointer-events: none; visibility: hidden;
    }}
    .flip-leaf.forward {{ right: 0; transform-origin: left center; }}
    .flip-leaf.backward {{ left: 0; transform-origin: right center; }}
    .flip-face {{
      position: absolute; inset: 0; backface-visibility: hidden; background: var(--panel);
      display: flex; align-items: center; justify-content: center; overflow: hidden;
    }}
    .flip-face.back {{ transform: rotateY(180deg); background: #e8dcc4; }}
    .flip-leaf.anim-forward {{
      visibility: visible; animation: hl-flip-fwd 720ms cubic-bezier(.2,.7,.2,1) forwards;
    }}
    .flip-leaf.anim-backward {{
      visibility: visible; animation: hl-flip-back 720ms cubic-bezier(.2,.7,.2,1) forwards;
    }}
    .book.flash {{
      box-shadow: 0 28px 70px #000c, 0 0 90px color-mix(in srgb, var(--gold) 55%, transparent);
    }}
    /* Reading / Listen panel — real HTML text for Safari Speak Screen */
    #reader {{
      display: none; max-width: 42rem; margin: 0 auto 1.5rem; padding: 1.25rem 1.5rem;
      background: var(--panel); color: var(--ink); border-radius: 12px;
      border: 1px solid color-mix(in srgb, var(--gold) 40%, transparent);
      box-shadow: 0 16px 40px #0008;
    }}
    #reader.open {{ display: block; }}
    #reader h2 {{ margin: 0 0 0.35rem; font-weight: 500; font-size: 1.35rem; }}
    #reader .meta {{
      margin: 0 0 1rem; color: var(--gold-dim); font: 0.9rem system-ui, sans-serif;
    }}
    #reader article {{ font-size: 1.2rem; line-height: 1.7; }}
    #reader article p {{ margin: 0 0 0.85rem; }}
    #reader .how {{
      margin-top: 1.25rem; padding-top: 0.85rem; border-top: 1px solid #cab995;
      font: 0.9rem system-ui, sans-serif; color: #5c4a3a;
    }}
    .hint {{
      max-width: 1100px; margin: 0.5rem auto 1.25rem; padding: 0 1rem;
      font: 0.95rem system-ui, sans-serif; color: #d4c4a8; line-height: 1.45;
    }}
    .err {{ color: #ffb4a8; }}
    body.reading-mode .stage-wrap {{ display: none; }}
    body.reading-mode #reader {{ display: block; margin-top: 1rem; }}
    @keyframes hl-flip-fwd {{
      0% {{ transform: rotateY(0); }} 100% {{ transform: rotateY(-178deg); }}
    }}
    @keyframes hl-flip-back {{
      0% {{ transform: rotateY(0); }} 100% {{ transform: rotateY(178deg); }}
    }}
    @keyframes hl-spine {{ 0%, 100% {{ opacity: 0.55; }} 50% {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .book::after {{ animation: none; }}
      .flip-leaf.anim-forward, .flip-leaf.anim-backward {{ animation-duration: 1ms; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>{title}</h1>
      <div class="by">{authors} · Pottermore Publishing (preview)</div>
    </div>
    <div class="tools">
      <button type="button" class="ghost" id="prev" disabled>← Prev</button>
      <span class="status" id="status">Loading…</span>
      <button type="button" id="next" disabled>Next →</button>
      <button type="button" id="toggle-read" aria-pressed="false">
        Reading / Listen
      </button>
    </div>
  </header>
  <div class="stage-wrap">
    <div class="book" id="book" aria-label="Open book two-page spread">
      <div class="spread" id="spread">
        <div class="page left">
          <div class="page-stack" id="stack-left">
            <canvas id="left"></canvas>
            <div class="textLayer" id="text-left"></div>
          </div>
        </div>
        <div class="page right">
          <div class="page-stack" id="stack-right">
            <canvas id="right"></canvas>
            <div class="textLayer" id="text-right"></div>
          </div>
        </div>
      </div>
      <div class="flip-leaf forward" id="flip" aria-hidden="true">
        <div class="flip-face front"><canvas id="flip-front"></canvas></div>
        <div class="flip-face back"><canvas id="flip-back"></canvas></div>
      </div>
    </div>
  </div>
  <section id="reader" lang="uk" aria-label="Reading text for Speak Screen">
    <h2 id="reader-title">{title}</h2>
    <p class="meta" id="reader-meta">Pages —</p>
    <article id="reader-article"><p>Loading text…</p></article>
    <p class="how">
      On iPad Safari: use <strong>aA → Listen to Page</strong>, or two-finger swipe down for
      <strong>Speak Screen</strong>. Install a Ukrainian voice under Settings → Accessibility →
      Spoken Content → Voices if needed. Display only — not on the HomeLib shelf.
    </p>
  </section>
  <p class="hint" id="hint">
    Tap <strong>Reading / Listen</strong> for selectable Ukrainian text (Speak Screen).
    Prev/Next turns the open book. Display only — not ingested.
  </p>
  <script type="module">
    import * as pdfjs from "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.8.69/pdf.min.mjs";
    pdfjs.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.8.69/pdf.worker.min.mjs";

    const bookId = {book_id_js};
    const title = {title_js};
    const pdfUrl = "/pdf/" + encodeURIComponent(bookId);
    const leftCanvas = document.getElementById("left");
    const rightCanvas = document.getElementById("right");
    const textLeft = document.getElementById("text-left");
    const textRight = document.getElementById("text-right");
    const stackLeft = document.getElementById("stack-left");
    const stackRight = document.getElementById("stack-right");
    const flipFront = document.getElementById("flip-front");
    const flipBack = document.getElementById("flip-back");
    const flip = document.getElementById("flip");
    const bookEl = document.getElementById("book");
    const status = document.getElementById("status");
    const prevBtn = document.getElementById("prev");
    const nextBtn = document.getElementById("next");
    const toggleRead = document.getElementById("toggle-read");
    const reader = document.getElementById("reader");
    const readerMeta = document.getElementById("reader-meta");
    const readerArticle = document.getElementById("reader-article");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let pdf = null;
    let leaf = 0;
    let busy = false;
    let reading = false;

    function wantsReadMode() {{
      const q = new URLSearchParams(location.search);
      const flag = (q.get("read") || "").toLowerCase();
      if (flag === "1" || flag === "true" || flag === "yes") return true;
      return location.hash === "#read";
    }}

    function setReadingMode(on) {{
      reading = !!on;
      document.body.classList.toggle("reading-mode", reading);
      reader.classList.toggle("open", reading);
      toggleRead.classList.toggle("active", reading);
      toggleRead.setAttribute("aria-pressed", reading ? "true" : "false");
      toggleRead.textContent = reading ? "Show book" : "Reading / Listen";
      document.getElementById("hint").hidden = reading;
      if (reading) {{
        fillReader(leaf);
        reader.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}
    }}

    async function pageText(pageNum) {{
      if (!pdf || pageNum < 1 || pageNum > pdf.numPages) return "";
      const page = await pdf.getPage(pageNum);
      const content = await page.getTextContent();
      const parts = [];
      for (const item of content.items) {{
        if (item && typeof item.str === "string") parts.push(item.str);
      }}
      return parts.join(" ").replace(/\\s+/g, " ").trim();
    }}

    async function fillReader(at) {{
      const rightNum = Math.min(at + 2, pdf.numPages);
      readerMeta.textContent = "Pages " + (at + 1) + "-" + rightNum + " / " + pdf.numPages;
      const [a, b] = await Promise.all([pageText(at + 1), pageText(at + 2)]);
      const paras = [];
      if (a) paras.push("<p>" + escapeHtml(a) + "</p>");
      if (b) paras.push("<p>" + escapeHtml(b) + "</p>");
      readerArticle.innerHTML = paras.length
        ? paras.join("")
        : "<p>(No extractable text on these pages — try Next, or open the publisher PDF.)</p>";
    }}

    function escapeHtml(s) {{
      return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }}

    async function paintLayer(pageNum, canvas, textDiv, stack) {{
      textDiv.replaceChildren();
      if (!pdf || pageNum < 1 || pageNum > pdf.numPages) {{
        const ctx = canvas.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, canvas.width || 1, canvas.height || 1);
        return;
      }}
      const page = await pdf.getPage(pageNum);
      const parent = stack.parentElement;
      const maxW = Math.max(120, parent.clientWidth - 12);
      const maxH = Math.max(120, parent.clientHeight - 12);
      const base = page.getViewport({{ scale: 1 }});
      const scale = Math.min(maxW / base.width, maxH / base.height);
      const viewport = page.getViewport({{ scale }});
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      stack.style.width = viewport.width + "px";
      stack.style.height = viewport.height + "px";
      textDiv.style.width = viewport.width + "px";
      textDiv.style.height = viewport.height + "px";
      textDiv.style.setProperty("--scale-factor", String(scale));
      await page.render({{ canvasContext: canvas.getContext("2d"), viewport }}).promise;
      const textContent = await page.getTextContent();
      const layer = new pdfjs.TextLayer({{
        textContentSource: textContent,
        container: textDiv,
        viewport,
      }});
      await layer.render();
    }}

    function lastLeft() {{
      return pdf.numPages % 2 === 0 ? pdf.numPages - 2 : pdf.numPages - 1;
    }}

    async function paintSpread(at) {{
      await Promise.all([
        paintLayer(at + 1, leftCanvas, textLeft, stackLeft),
        paintLayer(at + 2, rightCanvas, textRight, stackRight),
      ]);
      const rightNum = Math.min(at + 2, pdf.numPages);
      status.textContent = "Pages " + (at + 1) + "-" + rightNum + " / " + pdf.numPages;
      prevBtn.disabled = at <= 0;
      nextBtn.disabled = at + 2 >= pdf.numPages;
      document.title = title + " · " + (at + 1) + "-" + rightNum;
      await fillReader(at);
    }}

    async function paintCanvasOnly(pageNum, canvas, box) {{
      if (!pdf || pageNum < 1 || pageNum > pdf.numPages) return;
      const page = await pdf.getPage(pageNum);
      const parent = box || canvas.parentElement;
      const maxW = Math.max(120, parent.clientWidth - 12);
      const maxH = Math.max(120, parent.clientHeight - 12);
      const base = page.getViewport({{ scale: 1 }});
      const scale = Math.min(maxW / base.width, maxH / base.height);
      const viewport = page.getViewport({{ scale }});
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({{ canvasContext: canvas.getContext("2d"), viewport }}).promise;
    }}

    function runFlip(dir) {{
      return new Promise((resolve) => {{
        flip.className = "flip-leaf " + dir + " anim-" + dir;
        bookEl.classList.add("flash");
        const done = () => {{
          flip.className = "flip-leaf " + dir;
          bookEl.classList.remove("flash");
          flip.removeEventListener("animationend", done);
          resolve();
        }};
        if (reduce) {{ done(); return; }}
        flip.addEventListener("animationend", done);
        setTimeout(done, 800);
      }});
    }}

    async function showLeaf(nextLeaf, animate) {{
      if (!pdf || busy) return;
      const target = Math.max(0, Math.min(nextLeaf, lastLeft()));
      if (target === leaf && animate) return;
      const goingForward = target > leaf;
      busy = true;
      prevBtn.disabled = true;
      nextBtn.disabled = true;
      try {{
        if (animate && !reduce && !reading) {{
          const frontBox = flip.querySelector(".flip-face.front");
          const backBox = flip.querySelector(".flip-face.back");
          if (goingForward) {{
            await paintCanvasOnly(leaf + 2, flipFront, frontBox);
            await paintCanvasOnly(target + 1, flipBack, backBox);
            flip.className = "flip-leaf forward";
            await runFlip("forward");
          }} else {{
            await paintCanvasOnly(leaf + 1, flipFront, frontBox);
            await paintCanvasOnly(target + 2, flipBack, backBox);
            flip.className = "flip-leaf backward";
            await runFlip("backward");
          }}
        }}
        leaf = target;
        await paintSpread(leaf);
      }} finally {{
        busy = false;
        prevBtn.disabled = leaf <= 0;
        nextBtn.disabled = leaf + 2 >= pdf.numPages;
      }}
    }}

    toggleRead.addEventListener("click", () => setReadingMode(!reading));

    prevBtn.addEventListener("click", () => showLeaf(leaf - 2, true));
    nextBtn.addEventListener("click", () => showLeaf(leaf + 2, true));
    window.addEventListener("keydown", (e) => {{
      if (e.key === "ArrowLeft") showLeaf(leaf - 2, true);
      if (e.key === "ArrowRight") showLeaf(leaf + 2, true);
    }});

    try {{
      pdf = await pdfjs.getDocument(pdfUrl).promise;
      await showLeaf(0, false);
      if (wantsReadMode()) setReadingMode(true);
      window.addEventListener("resize", () => {{ if (!busy && !reading) paintSpread(leaf); }});
    }} catch (err) {{
      status.textContent = "Could not open PDF";
      status.className = "status err";
      console.error(err);
    }}
  </script>
</body>
</html>
"""
