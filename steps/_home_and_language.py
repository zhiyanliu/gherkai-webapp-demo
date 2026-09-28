"""主页与界面语言（需求 F1、F5）确定性 step 的判定逻辑——Nova Act 引擎侧（Python）。

只依赖 Playwright 的 Page，不注册 step：注册（薄壳）在 home_and_language.py，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
与 _home_and_language.mts 成对：选择器、判定口径、消息措辞保持一致，改一侧同步另一侧。

判定约定（与 _checks.py、_level_select.py 同一套）：
- 应用没达到期望 → 抛 AssertionError（step 记 failed），消息自带现场：期望与实际、页面地址、选择器。
- 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。

为什么页面标题与地址栏参数都在浏览器里读（document.title / location.href）：切换语言时应用用 history.replaceState
改地址、用 document.title 改标题，都不触发导航；在页面里轮询到条件成立为止最直接，两侧实现也一致。
比较前把标题与按钮文字的空白折成一个空格（浏览器标签上显示的就是折叠后的样子）；地址栏参数按 URL 解析后逐字比较，不折空白。

为什么「刷新页面」写成确定性 step：AI 引擎只能点、输入、滚动，没有「重新加载」这个动作；重新打开地址是导航不是刷新，
测不到「切换后写回地址栏、刷新后保持」这条需求（F5）。
"""
from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect

# --- 选择器（与 _home_and_language.mts 同一份） ---
SEL_LANG_TOGGLE = "#lang-toggle"   # 右上角的语言切换按钮，按钮上显示切换目标语言的名字（EN / 中文）

DEFAULT_TIMEOUT_MS = 5000   # 页面判定的等待上限（切换语言是同步的，5 秒足够容下 AI 点击步的收尾）
RELOAD_TIMEOUT_MS = 10000   # 刷新页面的加载上限（静态页面本机毫秒级，经隧道到云端浏览器也在几秒内）

# 浏览器里执行的判定（Python 版 Playwright 对字符串函数会调用并传参）。
_TITLE_EQUALS_JS = "(exp) => document.title.replace(/\\s+/g, ' ').trim() === exp"
_ELEMENT_TEXT_EQUALS_JS = """
({ sel, exp }) => { const el = document.querySelector(sel); return !!el && (el.textContent || '').replace(/\\s+/g, ' ').trim() === exp; }
"""
_QUERY_PARAM_EQUALS_JS = "({ name, value }) => new URL(location.href).searchParams.get(name) === value"
_QUERY_PARAM_JS = "(name) => new URL(location.href).searchParams.get(name)"


def normalize(text: str) -> str:
    """把所有空白（含换行）折成一个空格并去首尾。"""
    return " ".join(text.split())


# --- 现场信息 ---
def _where(page: Page, selector: str) -> str:
    return f"页面 {page.url}，选择器 {selector}"


def _safe_title(page: Page) -> str:
    """读页面标题给失败消息用；读不到就给占位，不让诊断本身再抛。"""
    try:
        return normalize(page.title())
    except Exception:  # noqa: BLE001  仅用于拼消息
        return "<读不到>"


def _safe_text(page: Page, selector: str) -> str:
    try:
        return normalize(page.locator(selector).first.text_content(timeout=500) or "")
    except Exception:  # noqa: BLE001  仅用于拼消息
        return "<读不到>"


def _safe_query_param(page: Page, name: str) -> str | None:
    """读地址栏里某个参数给失败消息用：没有这个参数返回 None，读不到给占位。"""
    try:
        return page.evaluate(_QUERY_PARAM_JS, name)
    except Exception:  # noqa: BLE001  仅用于拼消息
        return "<读不到>"


# --- 判定：页面标题 ---
def page_title_is(page: Page, title: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """页面标题（浏览器标签上的文字）在 timeout_ms 内恰为 title（空白归一、整段相等）。"""
    expected = normalize(title)
    try:
        page.wait_for_function(_TITLE_EQUALS_JS, arg=expected, timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        raise AssertionError(f"页面标题应为 {expected!r}，实际 {_safe_title(page)!r}（页面 {page.url}）") from e


# --- 判定：语言切换按钮 ---
def lang_toggle_shows(page: Page, label: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """语言切换按钮可见，且按钮上的文字在 timeout_ms 内恰为 label（空白归一、整段相等，「E」不算命中「EN」）。"""
    expected = normalize(label)
    try:
        expect(page.locator(SEL_LANG_TOGGLE)).to_be_visible(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(f"语言切换按钮没有显示（{_where(page, SEL_LANG_TOGGLE)}）") from e
    try:
        page.wait_for_function(_ELEMENT_TEXT_EQUALS_JS, arg={"sel": SEL_LANG_TOGGLE, "exp": expected}, timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        raise AssertionError(
            f"语言切换按钮应显示 {expected!r}，实际 {_safe_text(page, SEL_LANG_TOGGLE)!r}（{_where(page, SEL_LANG_TOGGLE)}）"
        ) from e


# --- 判定：地址栏参数 ---
def query_param_is(page: Page, name: str, value: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """地址栏（当前页面地址）里查询参数 name 的取值在 timeout_ms 内恰为 value（逐字相等）。

    应用用 history.replaceState 写回地址，不触发导航，所以在页面里轮询 location.href。
    """
    try:
        page.wait_for_function(_QUERY_PARAM_EQUALS_JS, arg={"name": name, "value": value}, timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        actual = _safe_query_param(page, name)
        actual_desc = "实际没有这个参数" if actual is None else f"实际 {actual!r}"
        raise AssertionError(f"地址栏的 {name} 参数应为 {value!r}，{actual_desc}（页面 {page.url}）") from e


# --- 动作：刷新页面 ---
def reload_page(page: Page, timeout_ms: int = RELOAD_TIMEOUT_MS) -> None:
    """重新加载当前页面（地址不变），等到 load 事件；加载不完成算应用没达到期望（AssertionError）。"""
    url = page.url
    try:
        page.reload(wait_until="load", timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        raise AssertionError(f"刷新页面在 {timeout_ms / 1000:g} 秒内没有加载完成（页面 {url}）") from e
