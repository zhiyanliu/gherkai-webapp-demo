"""选关页（需求 F2）确定性 step 的判定逻辑——Nova Act 引擎侧（Python）。

只依赖 Playwright 的 Page，不注册 step：注册（薄壳）在 level_select.py，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
与 _level_select.mts 成对：选择器、判定口径、消息措辞保持一致，改一侧同步另一侧。

判定约定（与 _checks.py 同一套）：
- 应用没达到期望 → 抛 AssertionError（step 记 failed），消息自带现场：期望与实际、当前显示的页面、页面地址、选择器。
- 用例写法错误（例如关卡名模板里没有字母 N）→ 抛 RuntimeError（step 记 error），与应用缺陷区分开。
- 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。

为什么每条判定都先等「选关页已显示」：应用四个页面的节点始终都在 DOM 里，只靠 hidden 切换显示；
关卡按钮在启动时就已渲染。不先判页面可见，「关卡按钮有 8 个」在主页上也会通过。

为什么按钮文案读 innerText 而不是 textContent：关卡名与副标题是两个块级元素，textContent 会把它们
黏成「第 1 组10 个生字」，innerText 才是用户看到的两行；比较前把所有空白折成一个空格。
"""
from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect

# --- 选择器（与 _level_select.mts 同一份） ---
SEL_LEVEL_SCREEN = "#level-screen"            # 选关页整块
SEL_LEVEL_TITLE = "#level-screen h2"          # 选关页标题
SEL_LEVEL_BUTTONS = "#level-grid button"      # 关卡按钮
SEL_ANY_BUTTON = "button"                     # 「页面上有 X 按钮」查的是任何可见按钮
# 四个页面的节点，只用于失败消息里说「当前显示的是哪一页」
SCREENS = (("主页", "#home-screen"), ("选关页", "#level-screen"), ("答题页", "#game-screen"), ("结算页", "#result-screen"))

DEFAULT_TIMEOUT_MS = 5000   # 页面判定的等待上限（页面切换动画 0.5 秒，5 秒足够）
LEVEL_NAME_PLACEHOLDER = "N"  # 关卡名模板里代入序号的字母：「第 N 组」→「第 1 组」「第 2 组」…

# 浏览器里执行的判定：可见（有布局盒）且 innerText 折叠空白后恰等于给定文字的按钮个数。
# 用 innerText 而非 accessible name：开始按钮里有一张 alt 文字的图片，accessible name 会带上它。
_VISIBLE_BUTTONS_WITH_TEXT_JS = """
({ sel, text }) => Array.from(document.querySelectorAll(sel))
  .filter(b => b.getClientRects().length > 0 && b.innerText.replace(/\\s+/g, ' ').trim() === text).length
"""
_VISIBLE_BUTTON_TEXTS_JS = """
(sel) => Array.from(document.querySelectorAll(sel))
  .filter(b => b.getClientRects().length > 0)
  .map(b => b.innerText.replace(/\\s+/g, ' ').trim())
"""
_VISIBLE_SCREENS_JS = """
(screens) => screens.filter(([, sel]) => { const el = document.querySelector(sel); return !!el && el.getClientRects().length > 0; })
  .map(([name]) => name)
"""


def normalize(text: str) -> str:
    """把所有空白（含换行）折成一个空格并去首尾：innerText 的两行 → 「第 1 组 10 个生字」。"""
    return " ".join(text.split())


# --- 现场信息 ---
def _where(page: Page, selector: str) -> str:
    return f"页面 {page.url}，选择器 {selector}"


def _safe_text(page: Page, selector: str) -> str:
    """读一个元素的文本给失败消息用；读不到就给占位，不让诊断本身再抛。"""
    try:
        return normalize(page.locator(selector).first.text_content(timeout=500) or "")
    except Exception:  # noqa: BLE001  仅用于拼消息
        return "<读不到>"


def _visible_screens(page: Page) -> str:
    try:
        names = page.evaluate(_VISIBLE_SCREENS_JS, [list(s) for s in SCREENS])
    except Exception:  # noqa: BLE001  仅用于拼消息
        return "<读不到>"
    return "、".join(names) if names else "没有任何页面"


def _visible_button_texts(page: Page) -> list[str]:
    try:
        return page.evaluate(_VISIBLE_BUTTON_TEXTS_JS, SEL_ANY_BUTTON)
    except Exception:  # noqa: BLE001  仅用于拼消息
        return ["<读不到>"]


def _level_button_texts(page: Page) -> list[str]:
    return [normalize(t) for t in page.locator(SEL_LEVEL_BUTTONS).all_inner_texts()]


# --- 前置：选关页已显示 ---
def _wait_level_screen(page: Page, timeout_ms: int) -> None:
    """选关页在 timeout_ms 内可见，否则 AssertionError 说明当前显示的是哪一页。"""
    try:
        expect(page.locator(SEL_LEVEL_SCREEN)).to_be_visible(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(
            f"选关页没有显示：当前显示的是 {_visible_screens(page)}（{_where(page, SEL_LEVEL_SCREEN)}）"
        ) from e


# --- 判定：标题、按钮个数、按钮文案 ---
def level_title_is(page: Page, title: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """选关页已显示，且标题文字恰为 title（空白归一）。"""
    _wait_level_screen(page, timeout_ms)
    try:
        expect(page.locator(SEL_LEVEL_TITLE)).to_have_text(title, timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(
            f"选关页标题应为 {title!r}，实际 {_safe_text(page, SEL_LEVEL_TITLE)!r}（{_where(page, SEL_LEVEL_TITLE)}）"
        ) from e


def level_button_count_is(page: Page, count: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """选关页已显示，且关卡按钮恰好 count 个。"""
    _wait_level_screen(page, timeout_ms)
    buttons = page.locator(SEL_LEVEL_BUTTONS)
    try:
        expect(buttons).to_have_count(count, timeout=timeout_ms)
    except AssertionError as e:
        texts = _level_button_texts(page)
        raise AssertionError(
            f"关卡按钮应有 {count} 个，实际 {len(texts)} 个：{texts}（{_where(page, SEL_LEVEL_BUTTONS)}）"
        ) from e


def expected_level_label(name_template: str, sub: str, index: int) -> str:
    """第 index 个（1 起）关卡按钮的期望文案（空白归一）：模板里的 N 代入序号，再接副标题。"""
    return normalize(f"{name_template.replace(LEVEL_NAME_PLACEHOLDER, str(index))} {sub}")


def level_buttons_labeled(page: Page, name_template: str, sub: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> list[str]:
    """每个关卡按钮的文案恰为「关卡名 + 副标题」：第 N 个按钮的关卡名是模板里的 N 代入 N。返回实际文案列表。

    模板里没有字母 N 是用例写法错误（RuntimeError）：那样每个按钮都会期望同一个名字。
    """
    if LEVEL_NAME_PLACEHOLDER not in name_template:
        raise RuntimeError(
            f"关卡名模板 {name_template!r} 里没有字母 {LEVEL_NAME_PLACEHOLDER}：要写成「第 N 组」这样，N 会依次代入 1、2、3…"
        )
    _wait_level_screen(page, timeout_ms)
    try:
        expect(page.locator(SEL_LEVEL_BUTTONS).first).to_be_visible(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(f"选关页上没有关卡按钮（{_where(page, SEL_LEVEL_BUTTONS)}）") from e
    texts = _level_button_texts(page)
    mismatches = []
    for i, actual in enumerate(texts, start=1):
        expected = expected_level_label(name_template, sub, i)
        if actual != expected:
            mismatches.append(
                f"第 {i} 个应标注「{name_template.replace(LEVEL_NAME_PLACEHOLDER, str(i))}」与「{sub}」，实际 {actual!r}"
            )
    if mismatches:
        raise AssertionError(
            f"关卡按钮的文案不符（共 {len(texts)} 个按钮，{len(mismatches)} 个不符）：" + "；".join(mismatches)
            + f"（{_where(page, SEL_LEVEL_BUTTONS)}）"
        )
    return texts


# --- 判定：页面上有某个按钮 ---
def has_visible_button(page: Page, text: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """页面上至少有一个可见的按钮，其文字（空白归一）恰为 text。整段相等，「返回」不算命中「返回主页」。"""
    expected = normalize(text)
    try:
        # 返回命中个数，0 为假值：wait_for_function 等到它非 0
        page.wait_for_function(_VISIBLE_BUTTONS_WITH_TEXT_JS, arg={"sel": SEL_ANY_BUTTON, "text": expected}, timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        raise AssertionError(
            f"页面上没有文字为 {expected!r} 的可见按钮，当前可见的按钮：{_visible_button_texts(page)}"
            f"（当前显示的是 {_visible_screens(page)}；{_where(page, SEL_ANY_BUTTON)}）"
        ) from e
