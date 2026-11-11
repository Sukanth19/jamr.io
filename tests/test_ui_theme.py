"""Tests for the "Vinyl" UI theme (warm cream paper, charcoal ink, burnt orange).

Checks that every page loads the theme, that the colours pass WCAG AA
contrast, that the CSS only uses tokens that exist, and that the restyle kept
every DOM hook the JavaScript relies on.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
CSS_DIR = FRONTEND / "css"
JS_DIR = FRONTEND / "js"

# route -> (html file, page script that queries its DOM)
PAGES = {
    "/": ("index.html", "landing.js"),
    "/login": ("login.html", "login.js"),
    "/discover": ("discover.html", "discover.js"),
    "/room": ("room.html", "room.js"),
    "/account": ("account.html", "account.js"),
    "/admin": ("admin.html", "admin.js"),
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def root_block() -> str:
    css = read(CSS_DIR / "main.css")
    match = re.search(r":root\s*\{(.*?)\n\}", css, re.S)
    assert match, "main.css must have a :root block"
    return match.group(1)


def root_tokens() -> dict:
    """Custom properties declared in main.css's :root block -> raw value."""
    return {name: value.strip() for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", root_block())}


def dark_tokens() -> dict:
    """Light tokens overridden by the :root[data-theme="dark"] block."""
    css = read(CSS_DIR / "main.css")
    match = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.S)
    assert match, 'main.css must have a :root[data-theme="dark"] block'
    tokens = dict(root_tokens())
    tokens.update({name: value.strip() for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", match.group(1))})
    return tokens


THEMES = {"light": root_tokens, "dark": dark_tokens}


def hex_token(name: str, theme: str = "light") -> str:
    value = THEMES[theme]()[name]
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), f"{name} ({theme}) should be a 6-digit hex colour, got {value}"
    return value


def contrast(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between two hex colours."""

    def luminance(hex_colour):
        channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    a, b = luminance(fg), luminance(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# ---------- Pages load the theme ----------


@pytest.mark.parametrize("route", list(PAGES))
def test_page_serves_and_links_theme(route):
    response = client.get(route)
    assert response.status_code == 200
    soup = BeautifulSoup(response.text, "html.parser")

    stylesheets = [link.get("href", "") for link in soup.find_all("link", rel="stylesheet")]
    assert "/static/css/main.css" in stylesheets
    fonts = " ".join(href for href in stylesheets if "fonts.googleapis.com" in href)
    for family in ("family=Inter", "family=Fraunces", "family=DM+Mono"):
        assert family in fonts, f"{family} not loaded on {route}"


@pytest.mark.parametrize("route", list(PAGES))
def test_page_title_keeps_brand(route):
    soup = BeautifulSoup(client.get(route).text, "html.parser")
    assert soup.title and "jamr.io" in soup.title.string


@pytest.mark.parametrize("route", list(PAGES))
def test_page_stylesheets_are_served(route):
    soup = BeautifulSoup(client.get(route).text, "html.parser")
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if href.startswith("/static/"):
            assert client.get(href).status_code == 200, f"{href} is not served"


# ---------- Design tokens ----------


def test_main_css_defines_vinyl_tokens():
    tokens = root_tokens()
    for token in ("--bg", "--surface", "--ink", "--accent", "--mustard", "--olive",
                  "--olive-soft", "--font-display", "--font-mono", "--shadow-press"):
        assert token in tokens, f"{token} missing from :root"
    assert "Fraunces" in tokens["--font-display"]
    assert "DM Mono" in tokens["--font-mono"]


def test_theme_is_light_cream():
    """The page background must be light (cream), with dark ink text."""
    bg, text = hex_token("--bg"), hex_token("--text")
    assert contrast(bg, "#ffffff") < 1.3, "--bg should be a light cream"
    assert contrast(text, "#000000") < 2, "--text should be a dark ink"


def test_no_old_theme_leftovers():
    """No Spotify green and nothing from the rejected neon theme."""
    for path in CSS_DIR.glob("*.css"):
        css = read(path).lower()
        assert "#1db954" not in css, f"spotify green in {path.name}"
        assert "29, 185, 84" not in css, f"spotify green rgba in {path.name}"
        assert "--accent-gradient" not in css, f"neon gradient in {path.name}"
        assert "space grotesk" not in css, f"neon font in {path.name}"
    for path in FRONTEND.glob("*.html"):
        assert "Space+Grotesk" not in read(path), f"neon font still loaded in {path.name}"


def test_every_css_var_is_defined():
    """Catches typos and tokens used by a page but never declared.
    Variables a rule declares for itself (like the vinyl's --size) count too."""
    defined = set(root_tokens())
    for path in CSS_DIR.glob("*.css"):
        defined |= set(re.findall(r"(--[a-z0-9-]+)\s*:", read(path)))
    missing = {}
    for path in CSS_DIR.glob("*.css"):
        undefined = set(re.findall(r"var\((--[a-z0-9-]+)", read(path))) - defined
        if undefined:
            missing[path.name] = sorted(undefined)
    assert not missing, f"undefined CSS variables: {missing}"


def test_css_braces_are_balanced():
    for path in CSS_DIR.glob("*.css"):
        css = re.sub(r"/\*.*?\*/", "", read(path), flags=re.S)
        assert css.count("{") == css.count("}"), f"unbalanced braces in {path.name}"


def test_headings_use_display_font():
    css = read(CSS_DIR / "main.css")
    assert re.search(r"h1,\s*h2,\s*h3\s*\{[^}]*font-family:\s*var\(--font-display\)", css)


# ---------- Accessibility: contrast ----------

# (foreground token, background token): every pair the theme puts text on
TEXT_PAIRS = [
    ("--text", "--bg"),
    ("--text", "--surface"),
    ("--text-muted", "--bg"),
    ("--text-muted", "--surface-2"),
    ("--text-faint", "--bg"),
    ("--text-faint", "--surface"),
    ("--text-faint", "--surface-2"),
    ("--accent", "--bg"),             # links
    ("--accent", "--surface"),        # links on cards
    ("--accent-text", "--accent"),    # primary buttons, Join the Jam
    ("--accent-text", "--accent-hover"),
    ("--accent-hover", "--accent-soft"),  # overseer badge
    ("--bg", "--ink"),                # own message bubbles, active tab, toasts
    ("--olive-ink", "--olive-soft"),  # your-genre chips
    ("--mustard-ink", "--mustard"),   # top match sticker
    ("--danger", "--bg"),
    ("--danger", "--surface"),
    ("--danger-ink", "--danger-soft"),     # error banners
    ("--role-mod-ink", "--role-mod-bg"),
    ("--role-admin-ink", "--role-admin-bg"),
]


@pytest.mark.parametrize("theme", list(THEMES))
@pytest.mark.parametrize("fg,bg", TEXT_PAIRS)
def test_text_contrast_meets_wcag_aa(theme, fg, bg):
    ratio = contrast(hex_token(fg, theme), hex_token(bg, theme))
    assert ratio >= 4.5, f"{theme}: {fg} on {bg} is {ratio:.2f}:1, needs 4.5:1"


def test_genre_colour_is_consistent():
    """'Your genres' use olive in the taste summary and on room cards."""
    main = read(CSS_DIR / "main.css")
    discover = read(CSS_DIR / "discover.css")
    assert re.search(r"\.chip-accent\s*\{[^}]*var\(--olive-soft\)", main)
    assert re.search(r"\.room-tag\.matched\s*\{[^}]*var\(--olive-soft\)", discover)


def test_message_delete_touch_target():
    css = read(CSS_DIR / "room.css")
    rule = re.search(r"\.message-delete\s*\{([^}]*)\}", css).group(1)
    height = re.search(r"min-height:\s*(\d+)px", rule)
    assert height and int(height.group(1)) >= 24, "message delete button must be at least 24px tall"


# ---------- Vinyl disc and motion ----------


def test_vinyl_component_exists():
    css = read(CSS_DIR / "main.css")
    assert re.search(r"\.vinyl\s*\{", css)
    assert "@keyframes vinyl-spin" in css


def test_reduced_motion_stops_records():
    css = read(CSS_DIR / "main.css")
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", css, re.S)
    assert block, "missing prefers-reduced-motion block"
    assert ".vinyl" in block.group(1)
    assert "animation: none" in block.group(1)


@pytest.mark.parametrize("route", ["/", "/room"])
def test_vinyl_is_decorative(route):
    soup = BeautifulSoup(client.get(route).text, "html.parser")
    discs = soup.select(".vinyl")
    assert discs, f"no vinyl on {route}"
    for disc in discs:
        assert disc.get("aria-hidden") == "true"


def test_discover_card_renders_vinyl_and_sticker():
    js = read(JS_DIR / "discover.js")
    assert '<span class="vinyl" aria-hidden="true"></span>' in js
    # Screen readers still hear "92% match"
    assert "${matchPercent}%<small> match</small>" in js
    assert "match-meter" not in js, "the match bar was dropped (it repeated the %)"


def test_room_spins_record_when_jam_live():
    js = read(JS_DIR / "room.js")
    assert "classList.toggle('jam-live'" in js
    assert ".jam-link-section.jam-live .vinyl" in read(CSS_DIR / "room.css")


# ---------- Landing behaviour ----------


def test_landing_stats_hidden_until_people_are_around():
    soup = BeautifulSoup(client.get("/").text, "html.parser")
    stats = soup.select_one("section.statistics")
    assert stats is not None and stats.has_attr("hidden"), "stats start hidden"
    js = read(JS_DIR / "landing.js")
    assert "stats.hidden = !(data.stats.active_users > 0)" in js


def test_landing_copy_unchanged():
    body = client.get("/").content
    assert b"Find your music community" in body
    assert b"Sign up" in body
    assert b'href="/login?mode=signup"' in body


# ---------- Dark mode ----------


def test_dark_theme_is_dark_with_light_ink():
    tokens = dark_tokens()
    assert contrast(tokens["--bg"], "#000000") < 1.5, "dark --bg should be near black"
    assert contrast(tokens["--text"], "#ffffff") < 1.4, "dark --text should be near white"
    css = read(CSS_DIR / "main.css")
    assert re.search(r':root\[data-theme="dark"\]\s*\{[^}]*color-scheme:\s*dark', css, re.S)


def test_dark_theme_overrides_every_colour_token():
    """Any light colour token not redefined for dark would leak a light colour."""
    css = read(CSS_DIR / "main.css")
    dark_block = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.S).group(1)
    overridden = set(re.findall(r"(--[a-z0-9-]+)\s*:", dark_block))
    colour_tokens = {name for name, value in root_tokens().items()
                     if re.match(r"(#[0-9a-fA-F]{3,8}|rgba?\(|url\()", value)}
    missing = sorted(colour_tokens - overridden)
    assert not missing, f"colour tokens with no dark value: {missing}"


def test_page_css_has_no_hard_coded_colours():
    """Page stylesheets must use tokens so they follow the theme."""
    for name in ("landing.css", "discover.css", "room.css", "auth.css", "admin.css"):
        css = re.sub(r"/\*.*?\*/", "", read(CSS_DIR / name), flags=re.S)
        hits = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", css)
        assert not hits, f"{name} hard-codes colours: {hits}"


@pytest.mark.parametrize("route", list(PAGES))
def test_page_has_theme_toggle(route):
    soup = BeautifulSoup(client.get(route).text, "html.parser")
    button = soup.find("button", id="theme-toggle")
    assert button is not None, f"no theme toggle on {route}"
    assert button.get("type") == "button"
    assert button.get("aria-label"), "toggle needs an accessible name"
    assert button.select_one("svg.icon-moon") and button.select_one("svg.icon-sun")
    for svg in button.find_all("svg"):
        assert svg.get("aria-hidden") == "true"


@pytest.mark.parametrize("route", list(PAGES))
def test_theme_script_runs_before_paint(route):
    """theme.js must be a blocking <head> script, or dark mode flashes light."""
    soup = BeautifulSoup(client.get(route).text, "html.parser")
    script = soup.head.find("script", src="/static/js/theme.js")
    assert script is not None, f"theme.js not in <head> on {route}"
    assert not script.has_attr("defer") and not script.has_attr("async")
    assert client.get("/static/js/theme.js").status_code == 200


# theme.js behaviour, run in Node against a fake browser

THEME_HARNESS = r"""
const fs = require('fs');
const [file, scenario] = [process.argv[2], JSON.parse(process.argv[3])];
const store = {};
if (scenario.saved) store['jamr-theme'] = scenario.saved;
const listeners = {};
const button = { attrs: {}, title: '', setAttribute(k, v) { this.attrs[k] = v; },
                 addEventListener(e, fn) { this.click = fn; } };
const classes = new Set();
global.localStorage = scenario.storageBlocked
    ? { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } }
    : { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); } };
const media = { matches: !!scenario.systemDark, addEventListener(e, fn) { media.onchange = fn; } };
global.window = { matchMedia: () => media, setTimeout: fn => fn() };
global.document = {
    documentElement: { dataset: {}, classList: { add: c => classes.add(c), remove: c => classes.delete(c) } },
    getElementById: id => (id === 'theme-toggle' ? button : null),
    addEventListener: (e, fn) => { listeners[e] = fn; },
};
eval(fs.readFileSync(file, 'utf8'));
const out = { initial: document.documentElement.dataset.theme };
listeners.DOMContentLoaded();
out.label = button.attrs['aria-label'];
if (scenario.systemFlipsTo !== undefined) {
    media.matches = scenario.systemFlipsTo; media.onchange();
    out.afterSystemFlip = document.documentElement.dataset.theme;
}
if (scenario.click) {
    button.click();
    out.afterClick = document.documentElement.dataset.theme;
    out.saved = scenario.storageBlocked ? null : (store['jamr-theme'] || null);
    out.labelAfterClick = button.attrs['aria-label'];
}
console.log(JSON.stringify(out));
"""


def run_theme_js(tmp_path, **scenario):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    harness = tmp_path / "harness.js"
    harness.write_text(THEME_HARNESS)
    result = subprocess.run(
        [node, str(harness), str(JS_DIR / "theme.js"), json.dumps(scenario)],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_theme_follows_system_dark(tmp_path):
    out = run_theme_js(tmp_path, systemDark=True)
    assert out["initial"] == "dark"
    assert out["label"] == "Switch to light mode"


def test_theme_follows_system_light(tmp_path):
    out = run_theme_js(tmp_path, systemDark=False)
    assert out["initial"] == "light"
    assert out["label"] == "Switch to dark mode"


def test_saved_choice_beats_system(tmp_path):
    out = run_theme_js(tmp_path, systemDark=True, saved="light")
    assert out["initial"] == "light"


def test_follows_live_system_change_until_user_picks(tmp_path):
    assert run_theme_js(tmp_path, systemDark=False, systemFlipsTo=True)["afterSystemFlip"] == "dark"
    # Once the user has chosen, a system change doesn't override it
    assert run_theme_js(tmp_path, systemDark=False, saved="light", systemFlipsTo=True)["afterSystemFlip"] == "light"


def test_toggle_switches_and_remembers(tmp_path):
    out = run_theme_js(tmp_path, systemDark=False, click=True)
    assert out["afterClick"] == "dark"
    assert out["saved"] == "dark"
    assert out["labelAfterClick"] == "Switch to light mode"


def test_toggle_still_works_when_storage_is_blocked(tmp_path):
    out = run_theme_js(tmp_path, systemDark=True, storageBlocked=True, click=True)
    assert out["initial"] == "dark"
    assert out["afterClick"] == "light"


# ---------- JS hooks survive the restyle ----------


@pytest.mark.parametrize("route", list(PAGES))
def test_page_keeps_every_id_its_script_uses(route):
    """Every getElementById in the page script must find something in the HTML
    (or be an element the script creates itself)."""
    html_file, script = PAGES[route]
    html = read(FRONTEND / html_file)
    js = read(JS_DIR / script)
    ids_in_html = {tag["id"] for tag in BeautifulSoup(html, "html.parser").find_all(id=True)}
    created_by_js = set(re.findall(r"""\.id\s*=\s*['"]([\w-]+)['"]""", js)) | set(
        re.findall(r"""id=["']([\w-]+)["']""", js)
    )
    queried = set(re.findall(r"""getElementById\(['"]([\w-]+)['"]\)""", js))
    missing = sorted(queried - ids_in_html - created_by_js)
    assert not missing, f"{html_file} lost ids used by {script}: {missing}"
