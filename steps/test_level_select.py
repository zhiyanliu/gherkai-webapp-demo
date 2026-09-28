"""steps/_level_select.py 的本地单测（Nova Act 侧判定逻辑）。

用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 test_ 开头的文件。
两类页面：
- 合成页：set_content 造出与应用同结构的最小四页骨架（同样的 id、同样靠 hidden 切换显示），关卡按钮个数、文案、
  当前显示哪一页可配置，用来走通过与失败两条路。
- 真应用：file:// 打开 app/index.html（英文界面加 ?lang=en），从主页点进选关页，验证选择器与真实文案；
  进入第 3 组后复用 _checks 里的进度与得分判定。

运行：uv sync && uv run playwright install chromium && uv run pytest
"""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

import _checks  # pytest 把测试所在目录放进导入路径
import _level_select as ls

APP_INDEX = Path(__file__).resolve().parent.parent / "app" / "index.html"


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


def zh_name(n: int) -> str:
    return f"第 {n} 组"


def en_name(n: int) -> str:
    return f"Group {n}"


def level_html(*, screen: str = "level", title: str = "选择关卡", count: int = 8, name: Callable[[int], str] = zh_name,
               sub: str = "10 个生字", overrides: dict[int, str] | None = None, back: str = "返回主页",
               start: str = "开始挑战") -> str:
    """与应用同结构的最小页面：四个页面节点都在 DOM 里、靠 hidden 切换；关卡按钮两行（关卡名、副标题）。

    overrides 按 1 起的序号替换某个按钮的整段 innerHTML，用来造出文案错误。
    """
    buttons = []
    for i in range(1, count + 1):
        inner = (overrides or {}).get(i, f'<div>{name(i)}</div><div>{sub}</div>')
        buttons.append(f"<button>{inner}</button>")
    hidden = lambda s: "" if s == screen else " hidden"  # noqa: E731
    return f"""<!doctype html><html><head><style>.hidden{{display:none}}</style></head><body>
<button id="lang-toggle">EN</button>
<section id="home-screen" class="{hidden('home').strip()}">
  <h1>识字大挑战</h1>
  <button id="start-btn"><img alt="开始按钮"><span>
      {start}
  </span></button>
</section>
<section id="level-screen" class="{hidden('level').strip()}">
  <h2>{title}</h2>
  <div id="level-grid">{''.join(buttons)}</div>
  <button id="back-home-btn">{back}</button>
</section>
<section id="game-screen" class="{hidden('game').strip()}">
  <span id="score-display">0</span><span id="current-q">1</span> / <span id="total-q">10</span>
</section>
<section id="result-screen" class="{hidden('result').strip()}">
  <button id="replay-btn">再玩一次</button><button id="home-btn">返回主页</button>
</section>
</body></html>"""


def load(page, **kw):
    page.set_content(level_html(**kw))


def show_level_after(page, delay_ms: int):
    """模拟点了开始挑战之后页面切换：delay_ms 后隐藏主页、显示选关页。"""
    page.evaluate(
        "(ms) => setTimeout(() => { document.getElementById('home-screen').classList.add('hidden');"
        " document.getElementById('level-screen').classList.remove('hidden'); }, ms)",
        delay_ms,
    )


# --- 标题 ---
def test_title_pass(page):
    load(page)
    ls.level_title_is(page, "选择关卡")


def test_title_waits_for_level_screen_to_appear(page):
    load(page, screen="home")
    show_level_after(page, 300)
    ls.level_title_is(page, "选择关卡", timeout_ms=3000)


def test_title_fails_when_level_screen_hidden_and_names_current_screen(page):
    load(page, screen="home")
    with pytest.raises(AssertionError, match=r"选关页没有显示：当前显示的是 主页.*#level-screen"):
        ls.level_title_is(page, "选择关卡", timeout_ms=300)


def test_title_mismatch_fails_with_expected_and_actual(page):
    load(page, title="选关")
    with pytest.raises(AssertionError, match=r"选关页标题应为 '选择关卡'，实际 '选关'.*#level-screen h2"):
        ls.level_title_is(page, "选择关卡", timeout_ms=300)


def test_title_is_whole_text_not_substring(page):
    load(page, title="请选择关卡")
    with pytest.raises(AssertionError, match=r"选关页标题应为 '选择关卡'，实际 '请选择关卡'"):
        ls.level_title_is(page, "选择关卡", timeout_ms=300)


# --- 按钮个数 ---
def test_button_count_pass(page):
    load(page)
    ls.level_button_count_is(page, 8)


def test_button_count_fails_listing_buttons(page):
    load(page, count=7)
    with pytest.raises(AssertionError, match=r"关卡按钮应有 8 个，实际 7 个：\['第 1 组 10 个生字', .*'第 7 组 10 个生字'\].*#level-grid button"):
        ls.level_button_count_is(page, 8, timeout_ms=300)


def test_button_count_fails_when_level_screen_hidden(page):
    # 关卡按钮在 DOM 里一直有 8 个：不先判选关页可见，这条在主页上也会通过
    load(page, screen="home")
    with pytest.raises(AssertionError, match=r"选关页没有显示：当前显示的是 主页"):
        ls.level_button_count_is(page, 8, timeout_ms=300)


# --- 按钮文案 ---
def test_labels_pass_zh(page):
    load(page)
    assert ls.level_buttons_labeled(page, "第 N 组", "10 个生字") == [f"第 {i} 组 10 个生字" for i in range(1, 9)]


def test_labels_pass_en(page):
    load(page, title="Choose a Level", name=en_name, sub="10 characters")
    ls.level_buttons_labeled(page, "Group N", "10 characters")


def test_labels_fail_on_wrong_group_number(page):
    load(page, overrides={3: "<div>第 4 组</div><div>10 个生字</div>"})
    with pytest.raises(AssertionError, match=r"关卡按钮的文案不符（共 8 个按钮，1 个不符）：第 3 个应标注「第 3 组」与「10 个生字」，实际 '第 4 组 10 个生字'（页面"):
        ls.level_buttons_labeled(page, "第 N 组", "10 个生字")


def test_labels_fail_on_wrong_subtitle_lists_every_mismatch(page):
    load(page, overrides={5: "<div>第 5 组</div><div>9 个生字</div>", 8: "<div>第 8 组</div>"})
    with pytest.raises(AssertionError, match=r"（共 8 个按钮，2 个不符）：第 5 个应标注.*实际 '第 5 组 9 个生字'；第 8 个应标注.*实际 '第 8 组'"):
        ls.level_buttons_labeled(page, "第 N 组", "10 个生字")


def test_labels_fail_when_lines_are_glued_together(page):
    # 两行之间没有任何分隔（同一个元素里）时用户看到的是「第 2 组10 个生字」，判不符
    load(page, overrides={2: "<div>第 2 组10 个生字</div>"})
    with pytest.raises(AssertionError, match=r"第 2 个应标注「第 2 组」与「10 个生字」，实际 '第 2 组10 个生字'"):
        ls.level_buttons_labeled(page, "第 N 组", "10 个生字")


def test_labels_template_without_placeholder_is_a_usage_error(page):
    load(page)
    with pytest.raises(RuntimeError, match=r"关卡名模板 '第 1 组' 里没有字母 N"):
        ls.level_buttons_labeled(page, "第 1 组", "10 个生字")


def test_labels_fail_when_no_buttons(page):
    load(page, count=0)
    with pytest.raises(AssertionError, match=r"选关页上没有关卡按钮.*#level-grid button"):
        ls.level_buttons_labeled(page, "第 N 组", "10 个生字", timeout_ms=300)


def test_labels_fail_when_level_screen_hidden(page):
    load(page, screen="home")
    with pytest.raises(AssertionError, match=r"选关页没有显示：当前显示的是 主页"):
        ls.level_buttons_labeled(page, "第 N 组", "10 个生字", timeout_ms=300)


def test_expected_label_substitutes_every_placeholder():
    assert ls.expected_level_label("第 N 组", "10 个生字", 3) == "第 3 组 10 个生字"
    assert ls.expected_level_label("Group N", "10 characters", 8) == "Group 8 10 characters"
    assert ls.expected_level_label("N-N", "x", 2) == "2-2 x"


# --- 页面上有某个按钮 ---
def test_has_button_pass_on_level_screen(page):
    load(page)
    ls.has_visible_button(page, "返回主页")


def test_has_button_reads_visible_text_not_accessible_name(page):
    # 开始按钮里有一张 alt 文字的图片、文字外面还有换行缩进：按 innerText 归一后仍应命中
    load(page, screen="home")
    ls.has_visible_button(page, "开始挑战")


def test_has_button_is_whole_text_not_substring(page):
    load(page)
    with pytest.raises(AssertionError, match=r"页面上没有文字为 '返回' 的可见按钮，当前可见的按钮：\['EN', '第 1 组 10 个生字', .*'返回主页'\]（当前显示的是 选关页；页面 .*选择器 button）"):
        ls.has_visible_button(page, "返回", timeout_ms=300)


def test_has_button_ignores_hidden_buttons(page):
    # 结算页里也有一个「返回主页」，但结算页没显示：主页上不算有这个按钮
    load(page, screen="home")
    with pytest.raises(AssertionError, match=r"页面上没有文字为 '返回主页' 的可见按钮，当前可见的按钮：\['EN', '开始挑战'\]（当前显示的是 主页"):
        ls.has_visible_button(page, "返回主页", timeout_ms=300)


def test_has_button_waits_for_late_render(page):
    load(page, screen="home")
    show_level_after(page, 300)
    ls.has_visible_button(page, "返回主页", timeout_ms=3000)


def test_has_button_normalizes_whitespace_in_expectation(page):
    load(page)
    ls.has_visible_button(page, "  返回主页 ")


# --- 真应用：选择器、真实文案、两种语言 ---
def open_level_screen(page, lang: str | None = None):
    page.goto(APP_INDEX.as_uri() + (f"?lang={lang}" if lang else ""))
    page.click("#start-btn")


def test_real_app_level_screen_zh(page):
    open_level_screen(page)
    ls.level_title_is(page, "选择关卡")
    ls.level_button_count_is(page, 8)
    ls.level_buttons_labeled(page, "第 N 组", "10 个生字")
    ls.has_visible_button(page, "返回主页")


def test_real_app_level_screen_en(page):
    open_level_screen(page, lang="en")
    ls.level_title_is(page, "Choose a Level")
    ls.level_button_count_is(page, 8)
    ls.level_buttons_labeled(page, "Group N", "10 characters")
    ls.has_visible_button(page, "Back to Home")


def test_real_app_home_page_does_not_pass_level_checks(page):
    page.goto(APP_INDEX.as_uri())
    ls.has_visible_button(page, "开始挑战")
    with pytest.raises(AssertionError, match=r"选关页没有显示：当前显示的是 主页"):
        ls.level_button_count_is(page, 8, timeout_ms=300)
    with pytest.raises(AssertionError, match=r"页面上没有文字为 '返回主页' 的可见按钮"):
        ls.has_visible_button(page, "返回主页", timeout_ms=300)


def test_real_app_back_to_home(page):
    open_level_screen(page)
    ls.has_visible_button(page, "返回主页")
    page.click("#back-home-btn")
    ls.has_visible_button(page, "开始挑战")
    with pytest.raises(AssertionError, match=r"选关页没有显示：当前显示的是 主页"):
        ls.level_title_is(page, "选择关卡", timeout_ms=300)


def test_real_app_group_3_starts_at_question_1_with_score_0(page):
    open_level_screen(page)
    page.locator("#level-grid button").nth(2).click()
    _checks.progress_is(page, "1", "10")
    _checks.score_is(page, "0")
    with pytest.raises(AssertionError, match=r"选关页没有显示：当前显示的是 答题页"):
        ls.level_title_is(page, "选择关卡", timeout_ms=300)


def test_synthetic_page_matches_real_app_structure():
    """合成页用的 id 都要在应用源码里真实存在，选择器漂了先在这里失败。"""
    src = APP_INDEX.read_text(encoding="utf-8")
    for needle in ('id="home-screen"', 'id="level-screen"', 'id="level-grid"', 'id="back-home-btn"', 'id="start-btn"',
                   'id="game-screen"', 'id="result-screen"', 'id="home-btn"'):
        assert needle in src, f"app/index.html 里找不到 {needle}"
    for _, sel in ls.SCREENS:
        assert f'id="{sel[1:]}"' in src, f"app/index.html 里找不到 {sel}"
    assert json.dumps(ls.SCREENS, ensure_ascii=False)  # SCREENS 可序列化，能原样传给页面里的 JS
