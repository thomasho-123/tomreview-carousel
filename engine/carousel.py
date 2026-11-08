"""Carousel engine v2 – multi-channel TikTok photo carousels (1080x1920 JPEG).

Usage:
  python3 carousel.py <channel.json> <post-dir>          # reads <post-dir>/spec.json, writes <post-dir>/out/slideNN.jpg + preview.jpg

channel.json:
{
  "channel_name": "Tom Review", "handle": "@tomreview6868",
  "avatar": "assets/avatar.jpg",            # relative to channel.json
  "theme": "paper-tech" | "fashion-editorial" | "sport-bold",
  "colors": {"accent": "#E2561A"},           # optional overrides of theme CSS variables
  "follow_cta": "Theo dõi để cập nhật mỗi ngày!"
}
spec.json: {"theme": optional per-post theme, "series": "...", "source": "Nguồn: ...",
            "slides": [{"label": "...", "html": "...", "credit": "..."}]}

Slide HTML building blocks (same class names in every theme):
  kicker, title (.xl/.md/.sm), sub, hl, accent, body (<b>), hand, num, card(<img src='img/x.jpg'>), bars/bar/lab,
  note(<p>, <p class='x'>), pills/pill(.on/.x), rule, steps(<li>), swatches/sw, rank, pc(pro/con), score, tag
Macros (replaced before render):
  [[stars 4]]                                   -> ★★★★☆
  [[look top=#hex bottom=#hex shoes=#hex]]      -> flat outfit illustration (also skirt=, dress=, bag=, outer=)
  [[swatch #hex Tên màu]]                       -> one colour chip
JPEG only: TikTok photo posts reject PNG.
"""
import json, sys, html, re, pathlib
from playwright.sync_api import sync_playwright

ENGINE = pathlib.Path(__file__).resolve().parent
FS = ENGINE / "node_modules/@fontsource"
W, H = 1080, 1920


def ff(family, folder, weight, style="normal"):
    """Load fontsource CSS (keeps unicode-range per subset so Vietnamese glyphs resolve correctly)."""
    css = FS / folder / (f"{weight}.css" if style == "normal" else f"{weight}-{style}.css")
    if not css.exists():
        return ""
    t = css.read_text()
    t = re.sub(r"font-family:\s*'[^']+'", f"font-family: '{family}'", t)
    return t.replace("url(./files/", f"url(file://{FS / folder / 'files'}/")


FONTS = "\n".join([
    *[ff("BVP", "be-vietnam-pro", w) for w in (300, 400, 500, 600, 700, 800, 900)],
    *[ff("PF", "playfair-display", w) for w in (400, 500, 700, 800, 900)],
    *[ff("PF", "playfair-display", w, "italic") for w in (400, 500, 700)],
    ff("Hand", "pangolin", 400),
    ff("Anton", "anton", 400),
    *[ff("Oswald", "oswald", w) for w in (400, 500, 600, 700)],
])

# ---------- shared layout (safe zone: x 80–900, y 150–1620) ----------
BASE = """
*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1920px;background:var(--paper);color:var(--ink);font-family:var(--f-body);position:relative;overflow:hidden}
.top{position:absolute;top:150px;left:80px;right:180px;display:flex;justify-content:space-between;font:var(--top-font);letter-spacing:var(--top-ls);text-transform:uppercase}
.top .n{color:var(--muted)}
.content{position:absolute;top:270px;left:80px;right:180px;bottom:380px}
.kicker{font:var(--kicker-font);letter-spacing:var(--top-ls);text-transform:uppercase;margin-bottom:18px;color:var(--kicker-color,var(--ink))}
.title{font:var(--title-font);letter-spacing:var(--title-ls);text-transform:var(--title-tt)}
.title.xl{font-size:calc(var(--title-size)*1.27)} .title.md{font-size:calc(var(--title-size)*.875)} .title.sm{font-size:calc(var(--title-size)*.77)}
.sub{font:var(--sub-font);margin-top:14px;color:var(--muted)}
.hl{background:linear-gradient(transparent 58%,var(--hl) 58%,var(--hl) 92%,transparent 92%)}
.accent{color:var(--accent)}
.body{font:var(--body-font);color:var(--body-color);margin-top:34px}
.body b{font-weight:800;color:var(--ink)}
.hand{font:var(--hand-font);color:var(--accent);transform:rotate(var(--hand-rot));transform-origin:left}
.num{font:var(--num-font);color:transparent;-webkit-text-stroke:3px var(--ink);margin-bottom:-6px}
.card{position:relative;margin-top:60px;width:820px;background:var(--card-bg);padding:18px;box-shadow:0 18px 40px rgba(0,0,0,.18);transform:rotate(var(--card-rot))}
.card img{display:block;width:100%;max-height:var(--card-h,330px);object-fit:cover}
.card:before{content:'';display:var(--tape);position:absolute;top:-26px;left:50%;width:150px;height:46px;margin-left:-75px;background:rgba(214,199,168,.85);transform:rotate(1deg)}
.card.tall img{max-height:700px}
.bars{margin-top:60px}
.bars .lab{font:var(--label-font);letter-spacing:.12em;margin:34px 0 14px;text-transform:uppercase}
.bar{display:flex;height:96px;border:4px solid var(--ink)}
.bar div{display:flex;align-items:center;justify-content:center;font:800 40px var(--f-body)}
.bar .f{background:var(--accent);color:var(--on-accent)}
.note{position:relative;background:var(--note-bg);margin-top:70px;padding:50px 30px 40px 100px;transform:rotate(-1.2deg);box-shadow:0 16px 34px rgba(0,0,0,.15);
 background-image:repeating-linear-gradient(transparent 0 78px,var(--note-line) 78px 80px);background-position:0 40px}
.note:after{content:'';position:absolute;left:78px;top:0;bottom:0;width:3px;background:#E3A39A}
.note p{font:var(--note-font);white-space:nowrap;color:var(--accent)}
.note p.x{color:#8C8F99;text-decoration:line-through}
.pills{display:flex;flex-wrap:wrap;gap:20px;margin-top:34px}
.pill{font:var(--pill-font);border:4px solid var(--ink);border-radius:60px;padding:10px 32px}
.pill.on{border-color:var(--accent);color:var(--accent)}
.pill.x{color:#8C8F99;border-color:#8C8F99;text-decoration:line-through}
.tag{display:inline-block;font:var(--label-font);letter-spacing:.1em;text-transform:uppercase;background:var(--accent);color:var(--on-accent);padding:8px 20px;margin-right:10px}
.rule{height:4px;background:var(--ink);margin:56px 0 40px}
.steps{list-style:none;counter-reset:s}
.steps li{counter-increment:s;font:var(--steps-font);margin-bottom:22px;display:flex;gap:22px}
.steps li:before{content:counter(s)'.';font-weight:800;min-width:46px;color:var(--accent)}
.swatches{display:flex;gap:26px;margin-top:50px;flex-wrap:wrap}
.sw{width:180px;text-align:center;font:var(--label-font);letter-spacing:.06em;text-transform:uppercase}
.sw i{display:block;width:180px;height:180px;border-radius:50%;background:var(--c);margin-bottom:16px;box-shadow:0 10px 24px rgba(0,0,0,.18),inset 0 0 0 3px rgba(255,255,255,.25)}
.rank{display:flex;gap:30px;align-items:flex-start;margin-top:40px}
.rank>b{font:var(--rank-font);color:var(--accent);line-height:.9;min-width:150px}
.rank h3{font:var(--rank-h-font);margin-bottom:8px}
.rank p{font:var(--body-font);color:var(--body-color);font-size:38px}
.pc{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:44px}
.pc>div{padding:28px;border:4px solid var(--ink)}
.pc h4{font:var(--label-font);letter-spacing:.12em;text-transform:uppercase;margin-bottom:14px}
.pc .pro h4{color:var(--accent)}
.pc p{font:400 36px/1.4 var(--f-body);margin-bottom:10px;color:var(--body-color)}
.score{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:20px;margin-top:50px;padding:40px 30px;background:var(--score-bg);color:var(--score-ink)}
.score .team{font:var(--label-font);font-size:40px;text-transform:uppercase;text-align:center}
.score .res{font:var(--rank-font);font-size:150px;color:var(--accent)}
.stars{color:var(--accent);letter-spacing:.08em}
.look{display:flex;gap:30px;justify-content:center;margin-top:40px}
.look.sm svg{height:420px}
.look svg{height:620px;filter:drop-shadow(0 18px 24px rgba(0,0,0,.18))}
.swipe{position:absolute;right:180px;top:1450px;display:flex;align-items:center;gap:18px}
.swipe span{font:var(--swipe-font);background:var(--swipe-bg);color:var(--swipe-ink);border-radius:22px;padding:10px 24px}
.swipe i{display:flex;align-items:center;justify-content:center;width:150px;height:96px;background:var(--button);color:var(--on-button);border-radius:18px 0 0 18px;font-style:normal;font-size:60px}
.brand{position:absolute;left:80px;top:1440px;display:flex;align-items:center;gap:22px}
.brand .av{width:110px;height:110px;border-radius:50%;object-fit:cover;border:4px solid var(--paper);box-shadow:0 0 0 4px var(--button)}
.brand small{display:block;font:500 28px var(--f-body);color:var(--muted)}
.brand b{font:800 36px var(--f-body)}
.src{position:absolute;left:80px;right:180px;top:1580px;font:400 24px var(--f-body);color:var(--muted)}
"""

THEMES = {
    # Tech news on dotted paper (Tom Review)
    "paper-tech": {
        "vars": {"paper": "#ECE8DF", "ink": "#1A1816", "muted": "#4A4640", "accent": "#E2561A", "on-accent": "#fff",
                 "hl": "rgba(255,122,47,.32)", "button": "#191970", "on-button": "#fff", "body-color": "#2b2825",
                 "card-bg": "#fff", "note-bg": "#FAF8F3", "note-line": "#C9D0E3", "swipe-bg": "#FAF8F3", "swipe-ink": "#1A1816",
                 "score-bg": "#1A1816", "score-ink": "#fff",
                 "f-body": "'BVP'", "title-size": "96px", "title-ls": "-.01em", "title-tt": "none", "top-ls": ".14em",
                 "top-font": "800 30px 'BVP'", "kicker-font": "800 34px 'BVP'", "title-font": "900 96px/1.08 'PF'",
                 "sub-font": "italic 700 50px 'PF'", "body-font": "400 44px/1.5 'BVP'", "hand-font": "400 50px/1.25 'Hand'",
                 "hand-rot": "-3deg", "num-font": "400 190px/1 'PF'", "label-font": "800 32px 'BVP'", "note-font": "400 44px/80px 'Hand'",
                 "pill-font": "400 46px 'Hand'", "steps-font": "500 46px/1.45 'BVP'", "rank-font": "900 150px 'PF'",
                 "rank-h-font": "800 52px/1.2 'BVP'", "swipe-font": "400 46px 'Hand'", "card-rot": "-1.6deg", "tape": "block"},
        "css": "body{background-image:radial-gradient(rgba(0,0,0,.09) 1.3px,transparent 1.4px);background-size:16px 16px}",
    },
    # Fashion / party wear: ivory magazine, burgundy + champagne, italic serif (no script fonts: they break Vietnamese accents)
    "fashion-editorial": {
        "vars": {"paper": "#F5F0E8", "ink": "#151312", "muted": "#7A6F66", "accent": "#8E2B3A", "on-accent": "#F5F0E8",
                 "hl": "rgba(200,169,126,.38)", "button": "#151312", "on-button": "#F5F0E8", "body-color": "#3A3330",
                 "card-bg": "#fff", "note-bg": "#FFFDF9", "note-line": "#EADFD3", "swipe-bg": "transparent", "swipe-ink": "#151312",
                 "score-bg": "#151312", "score-ink": "#F5F0E8",
                 "f-body": "'BVP'", "title-size": "100px", "title-ls": "-.015em", "title-tt": "none", "top-ls": ".32em",
                 "top-font": "600 26px 'BVP'", "kicker-font": "600 30px 'BVP'", "title-font": "italic 500 100px/1.04 'PF'",
                 "sub-font": "400 40px/1.4 'BVP'", "body-font": "300 44px/1.55 'BVP'", "hand-font": "italic 500 56px/1.2 'PF'",
                 "hand-rot": "-4deg", "num-font": "italic 400 200px/1 'PF'", "label-font": "600 28px 'BVP'",
                 "note-font": "italic 400 46px/80px 'PF'", "pill-font": "500 38px 'BVP'", "steps-font": "400 44px/1.5 'BVP'",
                 "rank-font": "italic 500 170px 'PF'", "rank-h-font": "italic 700 60px/1.15 'PF'", "swipe-font": "italic 500 46px 'PF'",
                 "card-rot": "0deg", "tape": "none", "card-h": "620px"},
        "css": """body:after{content:'';position:absolute;left:40px;right:40px;top:40px;bottom:40px;border:2px solid rgba(21,19,18,.18);pointer-events:none}
.top{border-bottom:2px solid var(--ink);padding-bottom:18px}
.card{box-shadow:none;border:2px solid var(--ink);padding:14px}
.pill{border-width:2px}.pc>div{border-width:2px}.bar{border-width:2px}.rule{height:2px}""",
    },
    # Sports wear / sports news: black, lime, condensed caps
    "sport-bold": {
        "vars": {"paper": "#0F1012", "ink": "#F4F4F0", "muted": "#9A9DA3", "accent": "#C6FF3D", "on-accent": "#0F1012",
                 "hl": "rgba(198,255,61,.28)", "button": "#C6FF3D", "on-button": "#0F1012", "body-color": "#D7D8DA",
                 "card-bg": "#1C1E22", "note-bg": "#1C1E22", "note-line": "#2A2D33", "swipe-bg": "transparent", "swipe-ink": "#F4F4F0",
                 "score-bg": "#1C1E22", "score-ink": "#F4F4F0",
                 "f-body": "'BVP'", "title-size": "124px", "title-ls": ".005em", "title-tt": "uppercase", "top-ls": ".18em",
                 "top-font": "600 30px 'Oswald'", "kicker-font": "600 36px 'Oswald'", "title-font": "400 118px/1.16 'Anton'",
                 "sub-font": "500 42px 'Oswald'", "body-font": "400 44px/1.5 'BVP'", "hand-font": "italic 600 52px/1.2 'Oswald'",
                 "hand-rot": "0deg", "num-font": "400 210px/1 'Anton'", "label-font": "600 32px 'Oswald'",
                 "note-font": "500 42px/80px 'Oswald'", "pill-font": "600 40px 'Oswald'", "steps-font": "500 46px/1.45 'BVP'",
                 "rank-font": "400 170px 'Anton'", "rank-h-font": "400 64px/1.2 'Anton'", "swipe-font": "600 42px 'Oswald'",
                 "card-rot": "0deg", "tape": "none"},
        "css": """body{background-image:repeating-linear-gradient(115deg,rgba(255,255,255,.035) 0 2px,transparent 2px 26px)}
body:before{content:'';position:absolute;left:0;top:0;width:24px;height:100%;background:var(--accent)}
.num{-webkit-text-stroke:3px var(--accent)}.note:after{background:var(--accent)}.note p.x{color:#5C6068}
.card{box-shadow:none}.hand{text-transform:uppercase}""",
    },
}


# ---------- macros ----------
def look_svg(a):
    skin = a.get("skin", "#E6C3A1")
    top, bottom, shoes = a.get("top"), a.get("bottom"), a.get("shoes", "#1B1B1B")
    skirt, dress, bag, outer = a.get("skirt"), a.get("dress"), a.get("bag"), a.get("outer")
    s = [f"<svg viewBox='0 0 300 720' xmlns='http://www.w3.org/2000/svg'>",
         f"<circle cx='150' cy='70' r='42' fill='{skin}'/><rect x='136' y='108' width='28' height='30' fill='{skin}'/>",
         f"<path d='M70 150 L58 340 L80 342 L96 190 Z M230 150 L242 340 L220 342 L204 190 Z' fill='{skin}'/>"]
    if dress:
        s.append(f"<path d='M95 135 Q150 120 205 135 L215 250 L262 560 Q150 590 38 560 L85 250 Z' fill='{dress}'/>")
        legs_top = 560
    else:
        if bottom:
            s.append(f"<path d='M92 300 L208 300 L222 640 L166 640 L150 380 L134 640 L78 640 Z' fill='{bottom}'/>")
            legs_top = 640
        elif skirt:
            s.append(f"<path d='M92 300 L208 300 L248 500 Q150 525 52 500 Z' fill='{skirt}'/>")
            legs_top = 505
        else:
            legs_top = 300
        s.append(f"<path d='M95 135 Q150 120 205 135 L218 310 L82 310 Z' fill='{top or '#ddd'}'/>")
    if legs_top < 640:
        s.append(f"<path d='M112 {legs_top} L134 {legs_top} L138 655 L118 655 Z M166 {legs_top} L188 {legs_top} L182 655 L162 655 Z' fill='{skin}'/>")
    s.append(f"<path d='M104 652 L142 652 L144 690 L90 690 Q92 664 104 652 Z M158 652 L196 652 Q208 664 210 690 L156 690 Z' fill='{shoes}'/>")
    if outer:
        s.append(f"<path d='M88 135 L130 128 L120 420 L72 410 Z M212 135 L170 128 L180 420 L228 410 Z' fill='{outer}' opacity='.96'/>"
                 f"<path d='M70 150 L50 360 L76 362 L96 190 Z M230 150 L250 360 L224 362 L204 190 Z' fill='{outer}'/>")
    if bag:
        s.append(f"<path d='M232 300 Q246 260 262 300' stroke='{bag}' stroke-width='6' fill='none'/><rect x='222' y='300' width='54' height='44' rx='8' fill='{bag}'/>")
    s.append("</svg>")
    return "".join(s)


def macros(t):
    t = re.sub(r"\[\[stars (\d)\]\]", lambda m: "<span class='stars'>" + "★" * int(m[1]) + "☆" * (5 - int(m[1])) + "</span>", t)
    t = re.sub(r"\[\[swatch (#[0-9A-Fa-f]{3,6}) ([^\]]+)\]\]", lambda m: f"<div class='sw' style='--c:{m[1]}'><i></i>{html.escape(m[2])}</div>", t)
    t = re.sub(r"\[\[look ([^\]]+)\]\]", lambda m: look_svg(dict(kv.split("=", 1) for kv in m[1].split())), t)
    return t


def page(slide, i, n, spec, ch, theme, avatar):
    vars_ = dict(THEMES[theme]["vars"]); vars_.update(ch.get("colors", {}))
    css = FONTS + ":root{" + ";".join(f"--{k}:{v}" for k, v in vars_.items()) + "}" + BASE + THEMES[theme]["css"]
    label = html.escape(slide.get("label") or spec.get("series", ""))
    parts = [f"<div class='top'><span>{label}</span><span class='n'>{i:02d} / {n:02d}</span></div>",
             f"<div class='content'>{macros(slide['html'])}</div>"]
    if i == 1 or i == n:
        av = f"<img class='av' src='file://{avatar}'>" if avatar else ""
        parts.append(f"<div class='brand'>{av}<div><small>{html.escape(ch['channel_name'])}</small><b>{html.escape(ch['handle'])}</b></div></div>")
    if i < n:
        parts.append("<div class='swipe'><span>Vuốt</span><i>&rarr;</i></div>")
    foot = slide.get("credit") or (spec.get("source") if i in (1, n) else "")
    if foot:
        parts.append(f"<div class='src'>{html.escape(foot)}</div>")
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(parts)}</body></html>"


def main(ch_path, post_dir):
    ch_path = pathlib.Path(ch_path).resolve(); ch = json.loads(ch_path.read_text())
    post = pathlib.Path(post_dir).resolve(); spec = json.loads((post / "spec.json").read_text())
    theme = spec.get("theme") or ch.get("theme", "paper-tech")
    avatar = (ch_path.parent / ch["avatar"]).resolve() if ch.get("avatar") else None
    out = post / "out"; out.mkdir(exist_ok=True)
    n = len(spec["slides"]); files = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": W, "height": H})
        for i, s in enumerate(spec["slides"], 1):
            hp = out / f"slide{i:02d}.html"
            hp.write_text(page(s, i, n, spec, ch, theme, avatar).replace("src='img/", f"src='file://{post}/img/"))
            pg.goto(f"file://{hp}"); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(150)
            f = out / f"slide{i:02d}.jpg"
            pg.screenshot(path=str(f), type="jpeg", quality=92); hp.unlink(); files.append(f)
        b.close()
    from PIL import Image
    cols = 4; rows = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 370, rows * 650), "white")
    for k, f in enumerate(files):
        sheet.paste(Image.open(f).resize((360, 640)), ((k % cols) * 370, (k // cols) * 650))
    sheet.save(post / "preview.jpg", quality=85)
    print("\n".join(map(str, files + [post / "preview.jpg"])))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
