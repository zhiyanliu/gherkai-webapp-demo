"""结算页（需求 F4）确定性 step 的判定逻辑——Nova Act 引擎侧（Python）。

只依赖 Playwright 的 Page，不注册 step：注册（薄壳）在 result.py，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
与 _result.mts 成对：选择器、判定口径、消息措辞保持一致，改一侧同步另一侧。

判定约定（与 _checks.py、_level_select.py 同一套）：
- 应用没达到期望 → 抛 AssertionError（step 记 failed），消息自带现场：期望与实际、当前显示的页面、页面地址、选择器。
- 用例写法错误（例如要答的题数超过本组剩余题数、「依次答对全部 N 题」没从第 1 题开始用）→ 抛 RuntimeError
  （step 记 error），与应用缺陷区分开。
- 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。

连答多题怎么做：每题复用 _checks 里按题库作答的 answer_correct / answer_wrong（查 steps/_vocabulary.json 点选项），
作答后等页面自动切换——进度里的题号变了（进入下一题）或结算页显示出来（答完最后一题）——再答下一题。
每题的等待上限是需求里的停留时长（答对 1.5 秒、答错 3 秒）加上页面判定的常规余量。这一步只保证「等到切题再答」，
切题时长是否精确为 1.5 秒 / 3 秒由答题页的 step（作答后 N 秒自动进入第 M 题）判，这里不重复。
每次作答前核对进度里的题号就是期望的那一题：应用跳题、或答完最后一题没进结算页而是出了第 11 题，都在这里报出来，
不留给后面的结算页判定去猜。

为什么结算页的每条判定都先等「结算页已显示」：四个页面的节点始终都在 DOM 里，只靠 hidden 切换显示；
最终得分与评语的节点带着上一局（或 HTML 里的占位）文字，不先判页面可见会在别的页面上误判通过。
"""
from __future__ import annotations

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect

try:
    from . import _checks  # worker 把 steps/ 挂在合成命名空间下（不入 sys.path），step 文件之间只能相对 import
except ImportError:
    import _checks  # 本地单测：pytest 把 steps/ 放进导入路径，顶层 import；worker 里这条路走不到

# --- 选择器（与 _result.mts 同一份） ---
SEL_RESULT_SCREEN = "#result-screen"      # 结算页整块
SEL_RESULT_TITLE = "#result-screen h2"    # 结算页标题
SEL_FINAL_SCORE = "#final-score"          # 最终得分
SEL_RESULT_MSG = "#result-msg"            # 评语
# 四个页面的节点，只用于失败消息里说「当前显示的是哪一页」
SCREENS = (("主页", "#home-screen"), ("选关页", "#level-screen"), ("答题页", "#game-screen"), ("结算页", "#result-screen"))

DEFAULT_TIMEOUT_MS = 5000     # 页面判定的等待上限（页面切换动画 0.5 秒，5 秒足够）
CORRECT_ADVANCE_MS = 1500     # 需求 F3：答对后停留 1.5 秒再切题
WRONG_ADVANCE_MS = 3000       # 需求 F3：答错后停留 3 秒再切题

KIND_CORRECT = "correct"
KIND_WRONG = "wrong"
OUTCOME_NEXT = "next"         # 作答后进入了下一题
OUTCOME_RESULT = "result"     # 作答后进入了结算页

# 浏览器里执行的判定（Python 版 Playwright 对字符串函数会调用并传参）。
# 作答后等切换：结算页有布局盒 → 'result'；题号不再是作答前的值 → 'next'；都没有 → null（wait_for_function 继续等）。
_ADVANCE_JS = """
({ qSel, before, resultSel }) => {
  const r = document.querySelector(resultSel);
  if (r && r.getClientRects().length > 0) return 'result';
  const q = document.querySelector(qSel);
  if (q && (q.textContent || '').trim() !== before) return 'next';
  return null;
}
"""
_VISIBLE_SCREENS_JS = """
(screens) => screens.filter(([, sel]) => { const el = document.querySelector(sel); return !!el && el.getClientRects().length > 0; })
  .map(([name]) => name)
"""


def normalize(text: str) -> str:
    """把所有空白（含换行）折成一个空格并去首尾。"""
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


def _live_question(page: Page) -> str:
    return _safe_text(page, _checks.SEL_CURRENT_Q)


def _kind_label(kind: str) -> str:
    return "对" if kind == KIND_CORRECT else "错"


# --- 前置：答题页已显示、读进度 ---
def _require_game_screen(page: Page, timeout_ms: int) -> None:
    """答题页在 timeout_ms 内可见，否则 AssertionError 说明当前显示的是哪一页。"""
    try:
        expect(page.locator(_checks.SEL_GAME_SCREEN)).to_be_visible(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(
            f"答题页没有显示，无法作答：当前显示的是 {_visible_screens(page)}（{_where(page, _checks.SEL_GAME_SCREEN)}）"
        ) from e


def _read_progress(page: Page) -> tuple[int, int]:
    """读进度里的当前题号与总题数（整数）；不是数字算应用没达到期望（AssertionError）。"""
    current = _safe_text(page, _checks.SEL_CURRENT_Q)
    total = _safe_text(page, _checks.SEL_TOTAL_Q)
    try:
        return int(current), int(total)
    except ValueError as e:
        raise AssertionError(
            f"进度里的当前题号与总题数应是数字，实际 {current!r} / {total!r}"
            f"（{_where(page, f'{_checks.SEL_CURRENT_Q} / {_checks.SEL_TOTAL_Q}')}）"
        ) from e


def _wait_advance(page: Page, question_before: str, timeout_ms: int) -> str | None:
    """作答后等页面自动切换：返回 'next'（进入下一题）、'result'（进入结算页）；timeout_ms 内都没发生返回 None。"""
    try:
        handle = page.wait_for_function(
            _ADVANCE_JS,
            arg={"qSel": _checks.SEL_CURRENT_Q, "before": question_before, "resultSel": SEL_RESULT_SCREEN},
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError:
        return None
    return handle.json_value()


# --- 动作：连答多题 ---
def answer_in_sequence(page: Page, correct: int, wrong: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> list[dict]:
    """从当前题起，按题库先依次答对 correct 题、再依次答错 wrong 题；每题作答后等自动切题（或进入结算页）再答下一题。

    返回每题的记录：题号、生字、点的拼音、答对还是答错、作答后进入了下一题还是结算页。
    要答的题数超过本组剩余题数、或两个数都是 0，是用例写法错误（RuntimeError）。
    应用没按需求走——作答后不切题、没答完就进结算页、跳题、答完最后一题没进结算页——都是 AssertionError，消息带题号与现场。
    """
    plan = [KIND_CORRECT] * correct + [KIND_WRONG] * wrong
    if not plan:
        raise RuntimeError("要答的题数是 0：答对与答错的题数不能都是 0")
    _require_game_screen(page, timeout_ms)
    start, total = _read_progress(page)
    remaining = total - start + 1
    if len(plan) > remaining:
        raise RuntimeError(
            f"要答 {len(plan)} 题（答对 {correct} 题、答错 {wrong} 题），但当前是第 {start} 题、共 {total} 题，"
            f"只剩 {remaining} 题可答（页面 {page.url}）"
        )

    records: list[dict] = []
    for i, kind in enumerate(plan):
        question = start + i
        live = _live_question(page)
        if live != str(question):
            raise AssertionError(
                f"第 {i + 1} 次作答前进度应显示第 {question} 题，实际显示第 {live} 题（已答 {i} 题，共 {total} 题；"
                f"{_where(page, _checks.SEL_CURRENT_Q)}）"
            )
        if kind == KIND_CORRECT:
            pinyin = _checks.answer_correct(page, timeout_ms)
        else:
            pinyin = _checks.answer_wrong(page, timeout_ms)
        word = _safe_text(page, _checks.SEL_WORD)  # 作答后页面至少停留 1.5 秒，这时读到的还是本题的生字
        delay_ms = CORRECT_ADVANCE_MS if kind == KIND_CORRECT else WRONG_ADVANCE_MS
        wait_ms = delay_ms + timeout_ms
        outcome = _wait_advance(page, str(question), wait_ms)
        if outcome is None:
            raise AssertionError(
                f"答{_kind_label(kind)}第 {question} 题（「{word}」选 {pinyin!r}）后 {wait_ms / 1000:g} 秒内没有自动进入下一题，"
                f"也没有进入结算页，仍显示第 {_live_question(page)} 题（共 {total} 题；{_where(page, _checks.SEL_CURRENT_Q)}）"
            )
        records.append({"question": question, "word": word, "pinyin": pinyin, "kind": kind, "outcome": outcome})
        is_last = i == len(plan) - 1
        if outcome == OUTCOME_RESULT and not is_last:
            raise AssertionError(
                f"答完第 {question} 题就进入了结算页，还有 {len(plan) - i - 1} 题没答（共 {total} 题；{_where(page, SEL_RESULT_SCREEN)}）"
            )
        if outcome == OUTCOME_NEXT and question == total:
            raise AssertionError(
                f"答完最后一题（第 {total} 题）后没有进入结算页，进度显示第 {_live_question(page)} 题"
                f"（{_where(page, _checks.SEL_CURRENT_Q)}）"
            )
    return records


def _answer_all(page: Page, kind: str, total: int, timeout_ms: int) -> list[dict]:
    """从第 1 题起把本组 total 题全部答对（或全部答错）。先核对进度里的总题数就是 total，且当前是第 1 题。"""
    _require_game_screen(page, timeout_ms)
    current, actual_total = _read_progress(page)
    if actual_total != total:
        raise AssertionError(f"本组应共 {total} 题，进度显示共 {actual_total} 题（{_where(page, _checks.SEL_TOTAL_Q)}）")
    if current != 1:
        raise RuntimeError(
            f"「依次答{_kind_label(kind)}全部 {total} 题」要在刚进入关卡、第 1 题时用，当前已是第 {current} 题（页面 {page.url}）"
        )
    if kind == KIND_CORRECT:
        return answer_in_sequence(page, total, 0, timeout_ms)
    return answer_in_sequence(page, 0, total, timeout_ms)


def answer_all_correct(page: Page, total: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> list[dict]:
    """从第 1 题起依次答对本组全部 total 题，答完进入结算页。返回每题的记录。"""
    return _answer_all(page, KIND_CORRECT, total, timeout_ms)


def answer_all_wrong(page: Page, total: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> list[dict]:
    """从第 1 题起依次答错本组全部 total 题，答完进入结算页。返回每题的记录。"""
    return _answer_all(page, KIND_WRONG, total, timeout_ms)


# --- 前置：结算页已显示 ---
def _wait_result_screen(page: Page, timeout_ms: int) -> None:
    """结算页在 timeout_ms 内可见，否则 AssertionError 说明当前显示的是哪一页。"""
    try:
        expect(page.locator(SEL_RESULT_SCREEN)).to_be_visible(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(
            f"结算页没有显示：当前显示的是 {_visible_screens(page)}（{_where(page, SEL_RESULT_SCREEN)}）"
        ) from e


def _expect_result_text(page: Page, selector: str, expected: str, what: str, timeout_ms: int) -> None:
    """结算页上某个元素的文本在 timeout_ms 内恰为 expected（空白归一、整段相等），否则 AssertionError 带期望与实际。"""
    try:
        expect(page.locator(selector)).to_have_text(expected, timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(f"{what}应为 {expected!r}，实际 {_safe_text(page, selector)!r}（{_where(page, selector)}）") from e


# --- 判定：结算页标题、最终得分、评语 ---
def result_title_is(page: Page, title: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """结算页已显示，且标题文字恰为 title。"""
    _wait_result_screen(page, timeout_ms)
    _expect_result_text(page, SEL_RESULT_TITLE, title, "结算页标题", timeout_ms)


def final_score_is(page: Page, score: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """结算页已显示，且最终得分的数值恰为 score（整段相等，「1」不算命中「10」）。"""
    _wait_result_screen(page, timeout_ms)
    _expect_result_text(page, SEL_FINAL_SCORE, score, "最终得分", timeout_ms)


def result_message_is(page: Page, message: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """结算页已显示，且评语文字恰为 message（含表情符号，整段相等）。"""
    _wait_result_screen(page, timeout_ms)
    _expect_result_text(page, SEL_RESULT_MSG, message, "评语", timeout_ms)
