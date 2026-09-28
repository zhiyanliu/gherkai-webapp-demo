"""答题页（需求 F3）确定性 step 的判定逻辑——Nova Act 引擎侧（Python）。

只依赖 Playwright 的 Page，不注册 step：注册（薄壳）在 quiz.py，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
与 _checks.mts 成对：选择器、题库来源、容差、消息措辞保持一致，改一侧同步另一侧。

判定约定：
- 应用没达到期望 → 抛 AssertionError（step 记 failed），消息自带现场：期望与实际、当前题号、页面地址、选择器。
- 用例写法错误（例如「作答后 N 秒自动进入」前面没有作答步）→ 抛 RuntimeError（step 记 error），与应用缺陷区分开。
- 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。

题库：steps/_vocabulary.json 是需求文档附录 A 题库表的副本，即规格；正确答案不显示在页面上，只能查表。判「答对」以规格为准，
test_checks.py 里两条单测：副本与附录 A 一致；应用源码与规格一致（判的是应用）。

自动切题时长的测法：作答点击前往页面注入一个只读探针（记录点击时刻、监听题号变化时刻），
之后的「作答后 N 秒自动进入第 M 题」步读探针算时长。探针不改应用行为，只是在页面里记两个时间戳，
这样中间隔着耗时的 AI 步（截图、模型往返要几秒）也量得准。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect

# --- 选择器（与 _checks.mts 同一份） ---
SEL_WORD = "#current-word"                 # 生字卡上的汉字
SEL_OPTIONS_BOX = "#options-container"     # 选项容器
SEL_OPTION = ".option-btn"                 # 单个拼音选项
SEL_OPTIONS = f"{SEL_OPTIONS_BOX} {SEL_OPTION}"
SEL_SCORE = "#score-display"               # 得分
SEL_GAME_SCREEN = "#game-screen"           # 答题页整块：四个页面的节点始终在 DOM 里、只靠隐藏切换，判进度与得分前先确认答题页可见
SEL_CURRENT_Q = "#current-q"               # 进度：当前题号
SEL_TOTAL_Q = "#total-q"                   # 进度：总题数
STATE_CORRECT = "correct"                  # 选项的「答对」状态（class）
STATE_WRONG = "wrong"                      # 选项的「答错」状态（class）

DEFAULT_TIMEOUT_MS = 5000       # 页面判定的等待上限
HIGHLIGHT_TIMEOUT_MS = 500      # 高亮状态在点击时同步写入，几百毫秒足够；答对只停留 1.5 秒，等太久会读到下一题
ADVANCE_TOLERANCE_MS = 400      # 自动切题时长的容差：能区分 1.5 秒与 1 秒 / 2 秒 / 3 秒，也容得下定时器的正常延迟

PROBE_KEY = "__gherkaiQuizProbe"
_VOCABULARY_PATH = Path(__file__).with_name("_vocabulary.json")

# 探针：装在作答点击之前。记录选项区第一次点击的时刻（capture 阶段，先于应用自己的 onclick），
# 用 MutationObserver 记录题号第一次变化的时刻与变化后的题号。重复安装时先卸掉上一个。
_PROBE_INSTALL_JS = """
({ key, qSel, boxSel, optSel }) => {
  const q = document.querySelector(qSel);
  const box = document.querySelector(boxSel);
  if (!q || !box) return false;
  const old = window[key];
  if (old && typeof old.dispose === 'function') old.dispose();
  const probe = { questionBefore: q.textContent.trim(), clickedAt: null, advancedAt: null, questionAfter: null };
  const onClick = (e) => {
    if (probe.clickedAt === null && e.target && e.target.closest && e.target.closest(optSel)) {
      probe.clickedAt = performance.now();
    }
  };
  box.addEventListener('click', onClick, true);
  const obs = new MutationObserver(() => {
    const now = q.textContent.trim();
    if (probe.advancedAt === null && now !== probe.questionBefore) {
      probe.advancedAt = performance.now();
      probe.questionAfter = now;
    }
  });
  obs.observe(q, { childList: true, characterData: true, subtree: true });
  probe.dispose = () => { obs.disconnect(); box.removeEventListener('click', onClick, true); };
  window[key] = probe;
  return true;
}
"""
_PROBE_READ_JS = """
(key) => {
  const p = window[key];
  if (!p) return null;
  return { questionBefore: p.questionBefore, clickedAt: p.clickedAt, advancedAt: p.advancedAt, questionAfter: p.questionAfter };
}
"""
_PROBE_ADVANCED_JS = "(key) => !!(window[key] && window[key].advancedAt !== null)"


# --- 题库 ---
@lru_cache(maxsize=1)
def load_vocabulary() -> dict[str, str]:
    """读 _vocabulary.json，返回 汉字 → 拼音。文件坏了或有重复汉字直接抛 ValueError（加载期 fail-loud）。"""
    items = json.loads(_VOCABULARY_PATH.read_text(encoding="utf-8"))
    vocab: dict[str, str] = {}
    for item in items:
        word, pinyin = item["word"], item["pinyin"]
        if word in vocab:
            raise ValueError(f"题库副本 {_VOCABULARY_PATH.name} 里汉字「{word}」重复")
        vocab[word] = pinyin
    if not vocab:
        raise ValueError(f"题库副本 {_VOCABULARY_PATH.name} 是空的")
    return vocab


# --- 现场信息 ---
def _where(page: Page, selector: str) -> str:
    return f"页面 {page.url}，选择器 {selector}"


def _safe_text(page: Page, selector: str) -> str:
    """读一个元素的文本给失败消息用；读不到就给占位，不让诊断本身再抛。"""
    try:
        return (page.locator(selector).first.text_content(timeout=500) or "").strip()
    except Exception:  # noqa: BLE001  仅用于拼消息
        return "<读不到>"


def _live_question(page: Page) -> str:
    return _safe_text(page, SEL_CURRENT_Q)


def _expect_text(page: Page, selector: str, expected: str, what: str, timeout_ms: int) -> None:
    """元素文本在 timeout_ms 内等于 expected（整段匹配、去首尾空白），否则 AssertionError 带期望与实际。"""
    try:
        expect(page.locator(selector)).to_have_text(expected, timeout=timeout_ms)
    except AssertionError as e:
        actual = _safe_text(page, selector)
        raise AssertionError(f"{what}应为 {expected!r}，实际 {actual!r}（{_where(page, selector)}）") from e


# --- 判定：进度、得分、选项个数 ---
def _require_game_screen(page: Page, timeout_ms: int) -> None:
    """答题页在 timeout_ms 内可见；否则 AssertionError。进度与得分的节点在主页上也存在且带着旧值，不先判这一步会在主页上误判通过。"""
    try:
        expect(page.locator(SEL_GAME_SCREEN)).to_be_visible(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(f"答题页未显示，无法判定进度与得分（{_where(page, SEL_GAME_SCREEN)}）") from e


def progress_is(page: Page, current: str, total: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """进度「当前题号 / 总题数」的数值；先要求答题页可见。"""
    _require_game_screen(page, timeout_ms)
    _expect_text(page, SEL_CURRENT_Q, current, "进度的当前题号", timeout_ms)
    _expect_text(page, SEL_TOTAL_Q, total, "进度的总题数", timeout_ms)


def score_is(page: Page, score: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """当前得分的数值；先要求答题页可见。"""
    _require_game_screen(page, timeout_ms)
    _expect_text(page, SEL_SCORE, score, "得分", timeout_ms)


def option_count_is(page: Page, count: int, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
    """本题的拼音选项恰好 count 个，且每个都有文字。"""
    options = page.locator(SEL_OPTIONS)
    try:
        expect(options).to_have_count(count, timeout=timeout_ms)
    except AssertionError as e:
        texts = [t.strip() for t in options.all_text_contents()]
        raise AssertionError(
            f"拼音选项应有 {count} 个，实际 {len(texts)} 个：{texts}（第 {_live_question(page)} 题；{_where(page, SEL_OPTIONS)}）"
        ) from e
    texts = [t.strip() for t in options.all_text_contents()]
    empty = [i + 1 for i, t in enumerate(texts) if not t]
    if empty:
        raise AssertionError(f"第 {empty} 个拼音选项没有文字：{texts}（{_where(page, SEL_OPTIONS)}）")


# --- 动作：按题库作答 ---
def _current_question(page: Page, timeout_ms: int) -> tuple[str, list[str]]:
    """等答题页就位（生字卡有字、选项已渲染），返回 (汉字, 选项文字列表)。"""
    options = page.locator(SEL_OPTIONS)
    try:
        expect(options.first).to_be_visible(timeout=timeout_ms)
        expect(page.locator(SEL_WORD)).not_to_be_empty(timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(
            f"答题页没有就位：生字卡或拼音选项没有出现（页面 {page.url}，选择器 {SEL_WORD} / {SEL_OPTIONS}）"
        ) from e
    word = (page.locator(SEL_WORD).text_content() or "").strip()
    texts = [t.strip() for t in options.all_text_contents()]
    return word, texts


def _lookup(page: Page, word: str) -> str:
    pinyin = load_vocabulary().get(word)
    if pinyin is None:
        raise AssertionError(
            f"生字卡上的「{word}」不在题库副本 {_VOCABULARY_PATH.name} 里：应用题库变了就同步这份副本（{_where(page, SEL_WORD)}）"
        )
    return pinyin


def _install_probe(page: Page) -> None:
    ok = page.evaluate(_PROBE_INSTALL_JS, {"key": PROBE_KEY, "qSel": SEL_CURRENT_Q, "boxSel": SEL_OPTIONS_BOX, "optSel": SEL_OPTION})
    if not ok:
        raise AssertionError(f"答题页没有就位：找不到进度或选项区（页面 {page.url}，选择器 {SEL_CURRENT_Q} / {SEL_OPTIONS_BOX}）")


def _click_option(page: Page, texts: list[str], index: int, timeout_ms: int) -> str:
    btn = page.locator(SEL_OPTIONS).nth(index)
    actual = (btn.text_content() or "").strip()
    if actual != texts[index]:
        raise AssertionError(
            f"拼音选项在读取后发生了变化：第 {index + 1} 个选项原为 {texts[index]!r}，现为 {actual!r}"
            f"（第 {_live_question(page)} 题；{_where(page, SEL_OPTIONS)}）"
        )
    _install_probe(page)
    try:
        btn.click(timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        raise AssertionError(f"拼音选项 {actual!r}（第 {index + 1} 个）无法点击：{str(e).splitlines()[0]}（{_where(page, SEL_OPTIONS)}）") from e
    return actual


def answer_correct(page: Page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    """按题库查出生字卡上汉字的拼音并点击那个选项。返回点击的拼音。"""
    word, texts = _current_question(page, timeout_ms)
    pinyin = _lookup(page, word)
    hits = [i for i, t in enumerate(texts) if t == pinyin]
    if not hits:
        raise AssertionError(f"「{word}」的正确拼音 {pinyin!r} 不在选项里：当前选项 {texts}（{_where(page, SEL_OPTIONS)}）")
    if len(hits) > 1:
        raise AssertionError(f"「{word}」的正确拼音 {pinyin!r} 在选项里出现了 {len(hits)} 次：{texts}（{_where(page, SEL_OPTIONS)}）")
    return _click_option(page, texts, hits[0], timeout_ms)


def answer_wrong(page: Page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    """按题库排除正确拼音，点击第一个错误选项。返回点击的拼音。"""
    word, texts = _current_question(page, timeout_ms)
    pinyin = _lookup(page, word)
    wrong = [i for i, t in enumerate(texts) if t != pinyin]
    if not wrong:
        raise AssertionError(f"选项里没有「{word}」（{pinyin!r}）以外的错误拼音：当前选项 {texts}（{_where(page, SEL_OPTIONS)}）")
    return _click_option(page, texts, wrong[0], timeout_ms)


def click_another_unhighlighted_option(page: Page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> str:
    """作答之后再点一个没有高亮的选项（验证一题只答一次）。返回点击的拼音。

    要紧跟在作答步之后：答对只停留 1.5 秒，中间隔着耗时的 AI 步就会点到下一题上。
    """
    highlighted = page.locator(f"{SEL_OPTIONS}.{STATE_CORRECT}, {SEL_OPTIONS}.{STATE_WRONG}")
    if highlighted.count() == 0:
        raise AssertionError(
            f"没有已作答的高亮选项（当前第 {_live_question(page)} 题）：要么作答后选项没有进入答对/答错状态，"
            f"要么已经自动切到下一题——这一步要紧跟在作答步之后，中间不能隔着耗时的 AI 步（{_where(page, SEL_OPTIONS)}）"
        )
    candidates = page.locator(f"{SEL_OPTIONS}:not(.{STATE_CORRECT}):not(.{STATE_WRONG})")
    if candidates.count() == 0:
        raise AssertionError(f"所有拼音选项都处于高亮状态，没有可再点的选项（{_where(page, SEL_OPTIONS)}）")
    btn = candidates.first
    text = (btn.text_content() or "").strip()
    try:
        btn.click(timeout=timeout_ms)
    except PlaywrightTimeoutError as e:
        raise AssertionError(f"拼音选项 {text!r} 无法点击：{str(e).splitlines()[0]}（{_where(page, SEL_OPTIONS)}）") from e
    return text


# --- 判定：作答后的高亮状态与自动切题 ---
def highlight_counts_are(page: Page, correct: int, wrong: int, timeout_ms: int = HIGHLIGHT_TIMEOUT_MS) -> None:
    """处于答对状态的选项 correct 个、答错状态的选项 wrong 个。"""
    loc_correct = page.locator(f"{SEL_OPTIONS}.{STATE_CORRECT}")
    loc_wrong = page.locator(f"{SEL_OPTIONS}.{STATE_WRONG}")
    try:
        expect(loc_correct).to_have_count(correct, timeout=timeout_ms)
        expect(loc_wrong).to_have_count(wrong, timeout=timeout_ms)
    except AssertionError as e:
        raise AssertionError(
            f"处于答对状态的选项应有 {correct} 个、答错状态的应有 {wrong} 个，实际答对 {loc_correct.count()} 个、答错 {loc_wrong.count()} 个"
            f"（第 {_live_question(page)} 题；{_where(page, SEL_OPTIONS)}）"
        ) from e


def auto_advance(page: Page, seconds: float, question: str, tolerance_ms: int = ADVANCE_TOLERANCE_MS) -> float:
    """作答后自动进入第 question 题，且从点击到切题的时长与 seconds 秒相差不超过 tolerance_ms。返回实测时长（秒）。

    读的是作答步装进页面的探针；这一步之前必须有 answer_correct / answer_wrong，否则是用例写法错误（RuntimeError）。
    """
    expected_ms = seconds * 1000
    probe = page.evaluate(_PROBE_READ_JS, PROBE_KEY)
    if probe is None:
        raise RuntimeError(
            "没有作答记录：「作答后 N 秒自动进入第 M 题」要用在「选择当前生字的正确拼音」或「选择一个错误的拼音」之后"
            f"（页面 {page.url}）"
        )
    if probe["clickedAt"] is None:
        raise RuntimeError(f"作答的点击没有被记录到：作答步点的不是拼音选项，或页面在作答后被重新加载（页面 {page.url}）")
    if probe["advancedAt"] is None:
        try:
            page.wait_for_function(_PROBE_ADVANCED_JS, arg=PROBE_KEY, timeout=expected_ms + tolerance_ms + 500)
        except PlaywrightTimeoutError as e:
            raise AssertionError(
                f"作答后 {seconds:g} 秒（容差 ±{tolerance_ms / 1000:g} 秒）内没有自动进入下一题，仍在第 {_live_question(page)} 题"
                f"（页面 {page.url}，选择器 {SEL_CURRENT_Q}）"
            ) from e
        probe = page.evaluate(_PROBE_READ_JS, PROBE_KEY)
    delay_ms = probe["advancedAt"] - probe["clickedAt"]
    if abs(delay_ms - expected_ms) > tolerance_ms:
        raise AssertionError(
            f"作答后自动进入下一题用了 {delay_ms / 1000:.2f} 秒，期望 {seconds:g} 秒（容差 ±{tolerance_ms / 1000:g} 秒）"
            f"（页面 {page.url}，选择器 {SEL_CURRENT_Q}）"
        )
    if probe["questionAfter"] != question:
        raise AssertionError(
            f"作答后自动进入的是第 {probe['questionAfter']} 题，期望第 {question} 题（现在显示第 {_live_question(page)} 题；"
            f"页面 {page.url}，选择器 {SEL_CURRENT_Q}）"
        )
    return delay_ms / 1000
