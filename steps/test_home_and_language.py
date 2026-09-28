"""steps/_home_and_language.py 的本地单测（Nova Act 侧判定逻辑）。

用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 test_ 开头的文件。
两类页面：
- 合成页：与应用同一套语言逻辑的最小页面（读 ?lang、改标题与按钮文字、replaceState 写回地址），行为可配置
  （是否写回地址、延迟多久生效、按钮是否隐藏、标题文案），用来走通过与失败两条路。合成页经 page.route 挂在一个
  http 地址上而不是 set_content：地址栏参数与刷新都需要页面有真实地址。
- 真应用：file:// 打开 app/index.html（英文界面加 ?lang=en），点右上角按钮切换，验证选择器、真实文案、地址写回与刷新后保持；
  答题中途切换复用 _checks 里的进度与得分判定。

运行：uv sync && uv run playwright install chromium && uv run pytest
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

import _checks  # pytest 把测试所在目录放进导入路径
import _home_and_language as hl

APP_INDEX = Path(__file__).resolve().parent.parent / "app" / "index.html"
ORIGIN = "http://app.test"   # 合成页挂的假地址：page.route 拦下、不走网络

ZH_TITLE, EN_TITLE = "识字大挑战 - 二年级上册", "Character Challenge - Grade 2, Volume 1"
ZH_LABEL, EN_LABEL = "EN", "中文"   # 按钮上是切换目标语言的名字：中文界面显示 EN，英文界面显示 中文


# --- 夹具 ---
@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    pg = browser.new_page()
    yield pg
    pg.close()


def lang_html(*, title_zh: str = ZH_TITLE, title_en: str = EN_TITLE, label_zh: str = ZH_LABEL, label_en: str = EN_LABEL,
              write_url: bool = True, apply_delay_ms: int = 0, toggle_hidden: bool = False) -> str:
    """与应用同一套语言逻辑的最小页面：启动读 ?lang，切换时（可选）replaceState 写回地址、（可延迟）改标题与按钮文字。"""
    cfg = {"titleZh": title_zh, "titleEn": title_en, "labelZh": label_zh, "labelEn": label_en,
           "writeUrl": write_url, "applyDelayMs": apply_delay_ms}
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title_zh}</title>
<style>.hidden{{display:none}}</style></head><body>
<button id="lang-toggle" class="{'hidden' if toggle_hidden else ''}">
  {label_zh}
</button>
<section id="home-screen"><h1 data-i18n="homeTitle">识字大挑战</h1><button id="start-btn">开始挑战</button></section>
<script>
  const CFG = {json.dumps(cfg, ensure_ascii=False)};
  const I18N = {{ zh: {{ title: CFG.titleZh, toggle: CFG.labelZh }}, en: {{ title: CFG.titleEn, toggle: CFG.labelEn }} }};
  let LANG = new URLSearchParams(location.search).get('lang') === 'en' ? 'en' : 'zh';
  function apply() {{
    document.title = I18N[LANG].title;
    document.getElementById('lang-toggle').textContent = I18N[LANG].toggle;
  }}
  function setLanguage(lang) {{
    LANG = lang;
    if (CFG.writeUrl) {{ const u = new URL(location.href); u.searchParams.set('lang', LANG); history.replaceState(null, '', u); }}
    if (CFG.applyDelayMs > 0) setTimeout(apply, CFG.applyDelayMs); else apply();
  }}
  document.getElementById('lang-toggle').onclick = () => setLanguage(LANG === 'zh' ? 'en' : 'zh');
  apply();
</script></body></html>"""


def serve(page, html: str, query: str = "") -> None:
    """把合成页挂到 ORIGIN 下并打开（query 形如 "?lang=en"）；刷新时同一份 html 再次被送出。"""
    page.route(f"{ORIGIN}/**", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html))
    page.goto(f"{ORIGIN}/index.html{query}")


# --- 页面标题 ---
def test_title_pass(page):
    serve(page, lang_html())
    hl.page_title_is(page, ZH_TITLE)


def test_title_pass_en_by_query(page):
    serve(page, lang_html(), "?lang=en")
    hl.page_title_is(page, EN_TITLE)


def test_title_waits_for_late_change(page):
    serve(page, lang_html(apply_delay_ms=300))
    page.click("#lang-toggle")
    hl.page_title_is(page, EN_TITLE, timeout_ms=3000)


def test_title_mismatch_fails_with_expected_actual_and_url(page):
    serve(page, lang_html(title_zh="识字挑战"))
    with pytest.raises(AssertionError, match=r"页面标题应为 '识字大挑战 - 二年级上册'，实际 '识字挑战'（页面 http://app\.test/index\.html）"):
        hl.page_title_is(page, ZH_TITLE, timeout_ms=300)


def test_title_is_whole_text_not_substring(page):
    serve(page, lang_html())
    with pytest.raises(AssertionError, match=r"页面标题应为 '识字大挑战'，实际 '识字大挑战 - 二年级上册'"):
        hl.page_title_is(page, "识字大挑战", timeout_ms=300)


def test_title_normalizes_whitespace_in_expectation(page):
    serve(page, lang_html())
    hl.page_title_is(page, "  识字大挑战  -   二年级上册 ")


# --- 语言切换按钮 ---
def test_toggle_pass_reads_text_with_whitespace_folded(page):
    # 合成页的按钮文字外面有换行缩进：折叠后恰为 EN
    serve(page, lang_html())
    hl.lang_toggle_shows(page, ZH_LABEL)


def test_toggle_pass_en(page):
    serve(page, lang_html(), "?lang=en")
    hl.lang_toggle_shows(page, EN_LABEL)


def test_toggle_waits_for_late_change(page):
    serve(page, lang_html(apply_delay_ms=300))
    page.click("#lang-toggle")
    hl.lang_toggle_shows(page, EN_LABEL, timeout_ms=3000)


def test_toggle_mismatch_fails_with_expected_actual_and_selector(page):
    serve(page, lang_html())
    with pytest.raises(AssertionError, match=r"语言切换按钮应显示 '中文'，实际 'EN'（页面 http://app\.test/index\.html，选择器 #lang-toggle）"):
        hl.lang_toggle_shows(page, EN_LABEL, timeout_ms=300)


def test_toggle_is_whole_text_not_substring(page):
    serve(page, lang_html())
    with pytest.raises(AssertionError, match=r"语言切换按钮应显示 'E'，实际 'EN'"):
        hl.lang_toggle_shows(page, "E", timeout_ms=300)


def test_toggle_hidden_fails_as_not_shown(page):
    serve(page, lang_html(toggle_hidden=True))
    with pytest.raises(AssertionError, match=r"语言切换按钮没有显示（页面 http://app\.test/index\.html，选择器 #lang-toggle）"):
        hl.lang_toggle_shows(page, ZH_LABEL, timeout_ms=300)


def test_toggle_missing_fails_as_not_shown(page):
    page.set_content("<button id='start-btn'>开始挑战</button>")
    with pytest.raises(AssertionError, match=r"语言切换按钮没有显示.*#lang-toggle"):
        hl.lang_toggle_shows(page, ZH_LABEL, timeout_ms=300)


# --- 地址栏参数 ---
def test_query_param_pass_from_start_url(page):
    serve(page, lang_html(), "?lang=en")
    hl.query_param_is(page, "lang", "en")


def test_query_param_pass_after_replace_state(page):
    serve(page, lang_html())
    page.click("#lang-toggle")
    hl.query_param_is(page, "lang", "en")
    page.click("#lang-toggle")
    hl.query_param_is(page, "lang", "zh")


def test_query_param_waits_for_late_replace_state(page):
    serve(page, lang_html())
    page.evaluate("setTimeout(() => history.replaceState(null, '', '?lang=en'), 300)")
    hl.query_param_is(page, "lang", "en", timeout_ms=3000)


def test_query_param_absent_fails_saying_so(page):
    serve(page, lang_html())
    with pytest.raises(AssertionError, match=r"地址栏的 lang 参数应为 'zh'，实际没有这个参数（页面 http://app\.test/index\.html）"):
        hl.query_param_is(page, "lang", "zh", timeout_ms=300)


def test_query_param_mismatch_fails_with_actual(page):
    serve(page, lang_html(write_url=False), "?lang=zh")
    page.click("#lang-toggle")   # 界面切了，但地址没写回
    hl.lang_toggle_shows(page, EN_LABEL)
    with pytest.raises(AssertionError, match=r"地址栏的 lang 参数应为 'en'，实际 'zh'（页面 http://app\.test/index\.html\?lang=zh）"):
        hl.query_param_is(page, "lang", "en", timeout_ms=300)


def test_query_param_is_exact_not_prefix(page):
    serve(page, lang_html(), "?lang=english")
    with pytest.raises(AssertionError, match=r"地址栏的 lang 参数应为 'en'，实际 'english'"):
        hl.query_param_is(page, "lang", "en", timeout_ms=300)


# --- 刷新页面 ---
def test_reload_keeps_url_and_reapplies_language(page):
    serve(page, lang_html())
    page.click("#lang-toggle")
    hl.query_param_is(page, "lang", "en")
    hl.reload_page(page)
    assert page.url == f"{ORIGIN}/index.html?lang=en"
    hl.page_title_is(page, EN_TITLE)
    hl.lang_toggle_shows(page, EN_LABEL)


def test_reload_timeout_fails_with_url(page):
    serve(page, lang_html())
    # 刷新时让请求一直挂着：超时算应用没达到期望
    page.unroute(f"{ORIGIN}/**")
    page.route(f"{ORIGIN}/**", lambda route: None)
    with pytest.raises(AssertionError, match=r"刷新页面在 0\.5 秒内没有加载完成（页面 http://app\.test/index\.html）"):
        hl.reload_page(page, timeout_ms=500)


# --- 真应用：选择器、真实文案、地址写回、刷新后保持、答题中途切换 ---
def open_app(page, lang: str | None = None):
    page.goto(APP_INDEX.as_uri() + (f"?lang={lang}" if lang else ""))


def test_real_app_home_zh(page):
    open_app(page)
    hl.page_title_is(page, ZH_TITLE)
    hl.lang_toggle_shows(page, ZH_LABEL)
    with pytest.raises(AssertionError, match=r"地址栏的 lang 参数应为 'zh'，实际没有这个参数"):
        hl.query_param_is(page, "lang", "zh", timeout_ms=300)   # 缺省中文时地址栏没有参数（需求：不带参数为中文）


def test_real_app_home_en_by_query(page):
    open_app(page, lang="en")
    hl.page_title_is(page, EN_TITLE)
    hl.lang_toggle_shows(page, EN_LABEL)
    hl.query_param_is(page, "lang", "en")


def test_real_app_toggle_and_back(page):
    open_app(page)
    page.click("#lang-toggle")
    hl.page_title_is(page, EN_TITLE)
    hl.lang_toggle_shows(page, EN_LABEL)
    hl.query_param_is(page, "lang", "en")
    page.click("#lang-toggle")
    hl.page_title_is(page, ZH_TITLE)
    hl.lang_toggle_shows(page, ZH_LABEL)
    hl.query_param_is(page, "lang", "zh")


def test_real_app_reload_keeps_english(page):
    open_app(page)
    page.click("#lang-toggle")
    hl.query_param_is(page, "lang", "en")
    hl.reload_page(page)
    hl.page_title_is(page, EN_TITLE)
    hl.lang_toggle_shows(page, EN_LABEL)
    hl.query_param_is(page, "lang", "en")


def test_real_app_toggle_mid_quiz_keeps_state(page):
    open_app(page)
    page.click("#start-btn")
    page.locator("#level-grid button").first.click()
    _checks.answer_correct(page)
    _checks.score_is(page, "1")
    _checks.progress_is(page, "2", "10")   # 等 1.5 秒自动切到第 2 题
    word = page.locator("#current-word").text_content()
    options = page.locator("#options-container .option-btn").all_text_contents()
    page.click("#lang-toggle")
    hl.lang_toggle_shows(page, EN_LABEL)
    hl.query_param_is(page, "lang", "en")
    hl.page_title_is(page, EN_TITLE)
    _checks.progress_is(page, "2", "10")
    _checks.score_is(page, "1")
    assert page.locator("#current-word").text_content() == word
    assert page.locator("#options-container .option-btn").all_text_contents() == options


def test_synthetic_page_matches_real_app_structure():
    """合成页用的选择器与文案都要在应用源码里真实存在，漂了先在这里失败。"""
    src = APP_INDEX.read_text(encoding="utf-8")
    assert f'id="{hl.SEL_LANG_TOGGLE[1:]}"' in src, f"app/index.html 里找不到 {hl.SEL_LANG_TOGGLE}"
    assert f"<title>{ZH_TITLE}</title>" in src
    for text in (ZH_TITLE, EN_TITLE, ZH_LABEL, EN_LABEL):
        assert text in src, f"app/index.html 里找不到文案 {text!r}"
