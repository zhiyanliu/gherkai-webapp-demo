"""steps/_checks.py 的本地单测（Nova Act 侧判定逻辑）。

用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 test_ 开头的文件。
两类页面：
- 合成页：set_content 造出与应用同结构的最小答题页，行为可配置（切题时长、是否加分、切到哪一题），用来走通过与失败两条路。
- 真应用：file:// 打开 app/index.html，从主页点到第 1 组，验证选择器、题库副本与真实的 1.5 秒 / 3 秒切题时长。

运行：uv sync && uv run playwright install chromium && uv run pytest
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

import _checks  # pytest 把测试所在目录放进导入路径

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


def quiz_html(word: str, options: list[str], correct: str, *, score: int = 0, current: int = 1, total: int = 10,
              correct_delay: int = 300, wrong_delay: int = 600, advance: bool = True, next_question: str = "2",
              increment_score: bool = True) -> str:
    """与应用同结构的最小答题页：同样的 id / class、同样的一题只答一次与切题逻辑，时长可配。"""
    cfg = {"correctDelay": correct_delay, "wrongDelay": wrong_delay, "advance": advance,
           "nextQuestion": next_question, "incrementScore": increment_score}
    return f"""<!doctype html><html><body>
<div><span id="score-display">{score}</span></div>
<div><span id="current-q">{current}</span> / <span id="total-q">{total}</span></div>
<div><span id="current-word">{word}</span></div>
<div id="options-container"></div>
<script>
  const CORRECT = {json.dumps(correct, ensure_ascii=False)};
  const OPTIONS = {json.dumps(options, ensure_ascii=False)};
  const CFG = {json.dumps(cfg)};
  let answering = false;
  const box = document.getElementById('options-container');
  function render() {{
    box.innerHTML = '';
    OPTIONS.forEach(opt => {{
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.textContent = opt;
      b.onclick = () => handle(b, opt);
      box.appendChild(b);
    }});
  }}
  function handle(btn, selected) {{
    if (answering) return;
    answering = true;
    const ok = selected === CORRECT;
    if (ok) {{
      btn.classList.add('correct');
      if (CFG.incrementScore) {{
        const s = document.getElementById('score-display');
        s.textContent = String(Number(s.textContent) + 1);
      }}
    }} else {{
      btn.classList.add('wrong');
      document.querySelectorAll('.option-btn').forEach(b => {{ if (b.textContent === CORRECT) b.classList.add('correct'); }});
    }}
    if (CFG.advance) {{
      setTimeout(() => {{
        document.getElementById('current-q').textContent = CFG.nextQuestion;
        answering = false;
        render();
      }}, ok ? CFG.correctDelay : CFG.wrongDelay);
    }}
  }}
  render();
</script></body></html>"""


WORD, CORRECT = "两", "liǎng"
OPTIONS = ["nǎ", "liǎng", "pí", "dù"]


def load(page, **kw):
    page.set_content(quiz_html(WORD, OPTIONS, CORRECT, **kw))


# --- 题库副本与应用源码一致 ---
def test_vocabulary_matches_app_source():
    src = APP_INDEX.read_text(encoding="utf-8")
    found = re.search(r"const VOCABULARY = \[(.*?)\];", src, re.S)
    assert found is not None, "app/index.html 里找不到 VOCABULARY 表"
    block = found.group(1)
    items = re.findall(r"\{\s*word:\s*'([^']+)',\s*pinyin:\s*'([^']+)'\s*\}", block)
    from_app = dict(items)
    assert len(items) == len(from_app) == 81, "应用题库应有 81 个不重复的生字（需求第 4 节）"
    assert _checks.load_vocabulary() == from_app, "steps/_vocabulary.json 与 app/index.html 的 VOCABULARY 不一致，同步这份副本"


# --- 进度、得分、选项个数 ---
def test_progress_and_score_pass(page):
    load(page)
    _checks.progress_is(page, "1", "10")
    _checks.score_is(page, "0")


def test_progress_fails_with_context(page):
    load(page, current=2)
    with pytest.raises(AssertionError, match=r"进度的当前题号应为 '1'，实际 '2'.*#current-q"):
        _checks.progress_is(page, "1", "10", timeout_ms=300)


def test_score_is_whole_text_not_substring(page):
    load(page, score=10)
    with pytest.raises(AssertionError, match=r"得分应为 '1'，实际 '10'.*#score-display"):
        _checks.score_is(page, "1", timeout_ms=300)


def test_score_waits_for_late_update(page):
    load(page)
    page.evaluate("setTimeout(() => document.getElementById('score-display').textContent = '1', 200)")
    _checks.score_is(page, "1", timeout_ms=2000)


def test_option_count_pass(page):
    load(page)
    _checks.option_count_is(page, 4)


def test_option_count_fails_with_options_listed(page):
    page.set_content(quiz_html(WORD, ["nǎ", "liǎng", "pí"], CORRECT))
    with pytest.raises(AssertionError, match=r"拼音选项应有 4 个，实际 3 个：\['nǎ', 'liǎng', 'pí'\].*#options-container \.option-btn"):
        _checks.option_count_is(page, 4, timeout_ms=300)


def test_option_count_fails_on_empty_option_text(page):
    page.set_content(quiz_html(WORD, ["nǎ", "liǎng", "", "dù"], CORRECT))
    with pytest.raises(AssertionError, match=r"第 \[3\] 个拼音选项没有文字"):
        _checks.option_count_is(page, 4, timeout_ms=300)


# --- 按题库作答 ---
def test_answer_correct_clicks_the_vocabulary_pinyin(page):
    load(page)
    assert _checks.answer_correct(page) == CORRECT
    assert page.locator("#options-container .option-btn.correct").text_content() == CORRECT
    _checks.score_is(page, "1")


def test_answer_correct_waits_for_options_to_render(page):
    page.set_content('<span id="current-q">1</span><span id="current-word"></span><div id="options-container"></div>')
    page.evaluate("""() => setTimeout(() => {
        document.getElementById('current-word').textContent = '两';
        const box = document.getElementById('options-container');
        ['pí', 'liǎng'].forEach(t => { const b = document.createElement('button'); b.className = 'option-btn'; b.textContent = t; box.appendChild(b); });
    }, 300)""")
    assert _checks.answer_correct(page, timeout_ms=3000) == CORRECT


def test_answer_correct_unknown_word_fails(page):
    page.set_content(quiz_html("龘", OPTIONS, CORRECT))
    with pytest.raises(AssertionError, match=r"「龘」不在题库副本 _vocabulary\.json 里"):
        _checks.answer_correct(page)


def test_answer_correct_missing_option_fails(page):
    page.set_content(quiz_html(WORD, ["nǎ", "pí", "dù", "tā"], CORRECT))
    with pytest.raises(AssertionError, match=r"「两」的正确拼音 'liǎng' 不在选项里：当前选项 \['nǎ', 'pí', 'dù', 'tā'\]"):
        _checks.answer_correct(page)


def test_answer_correct_duplicate_correct_option_fails(page):
    page.set_content(quiz_html(WORD, ["liǎng", "pí", "liǎng", "dù"], CORRECT))
    with pytest.raises(AssertionError, match=r"在选项里出现了 2 次"):
        _checks.answer_correct(page)


def test_answer_correct_page_not_ready_fails(page):
    page.set_content('<div id="options-container"></div><span id="current-word"></span>')
    with pytest.raises(AssertionError, match=r"答题页没有就位"):
        _checks.answer_correct(page, timeout_ms=300)


def test_answer_wrong_clicks_first_non_correct_option(page):
    load(page)
    assert _checks.answer_wrong(page) == "nǎ"
    assert page.locator("#options-container .option-btn.wrong").text_content() == "nǎ"
    assert page.locator("#options-container .option-btn.correct").text_content() == CORRECT
    _checks.score_is(page, "0")


def test_answer_wrong_with_only_correct_options_fails(page):
    page.set_content(quiz_html(WORD, ["liǎng"], CORRECT))
    with pytest.raises(AssertionError, match=r"没有「两」（'liǎng'）以外的错误拼音"):
        _checks.answer_wrong(page)


# --- 一题只答一次 ---
def test_click_another_option_after_answer_changes_nothing(page):
    load(page)
    _checks.answer_correct(page)
    other = _checks.click_another_unhighlighted_option(page)
    assert other in OPTIONS and other != CORRECT
    _checks.score_is(page, "1")
    _checks.highlight_counts_are(page, 1, 0)


def test_click_another_without_an_answer_fails(page):
    load(page)
    with pytest.raises(AssertionError, match=r"没有已作答的高亮选项（当前第 1 题）"):
        _checks.click_another_unhighlighted_option(page)


def test_highlight_counts_fail_with_actuals(page):
    load(page)
    _checks.answer_wrong(page)
    with pytest.raises(AssertionError, match=r"应有 1 个、答错状态的应有 0 个，实际答对 1 个、答错 1 个（第 1 题"):
        _checks.highlight_counts_are(page, 1, 0)


# --- 自动切题时长 ---
def test_auto_advance_measures_delay_and_new_question(page):
    load(page, correct_delay=600)
    _checks.answer_correct(page)
    measured = _checks.auto_advance(page, 0.6, "2")
    assert 0.55 <= measured <= 0.9


def test_auto_advance_still_measures_after_a_slow_intermediate_step(page):
    load(page, correct_delay=600)
    _checks.answer_correct(page)
    time.sleep(1.5)  # 模拟中间隔着一条耗时的 AI 步：切题早已发生，时长仍由页面里的探针给出
    measured = _checks.auto_advance(page, 0.6, "2")
    assert 0.55 <= measured <= 0.9


def test_auto_advance_wrong_delay_fails(page):
    load(page, wrong_delay=600)
    _checks.answer_wrong(page)
    with pytest.raises(AssertionError, match=r"作答后自动进入下一题用了 0\.6\d 秒，期望 1\.5 秒（容差 ±0\.4 秒）"):
        _checks.auto_advance(page, 1.5, "2")


def test_auto_advance_never_advances_fails(page):
    load(page, advance=False)
    _checks.answer_correct(page)
    with pytest.raises(AssertionError, match=r"作答后 0\.5 秒（容差 ±0\.4 秒）内没有自动进入下一题，仍在第 1 题"):
        _checks.auto_advance(page, 0.5, "2")


def test_auto_advance_to_unexpected_question_fails(page):
    load(page, correct_delay=300, next_question="3")
    _checks.answer_correct(page)
    with pytest.raises(AssertionError, match=r"自动进入的是第 3 题，期望第 2 题"):
        _checks.auto_advance(page, 0.3, "2")


def test_auto_advance_without_an_answer_is_a_usage_error(page):
    load(page)
    with pytest.raises(RuntimeError, match=r"没有作答记录"):
        _checks.auto_advance(page, 1.5, "2")


def test_answering_twice_in_a_row_resets_the_probe(page):
    load(page, correct_delay=300)
    _checks.answer_correct(page)
    _checks.auto_advance(page, 0.3, "2")
    page.evaluate("document.getElementById('current-word').textContent = '两'")
    _checks.answer_correct(page)
    # 合成页每次都切到 "2"：第二次作答后题号不变，探针（新起点 "2"）就不会记到切题 → 说明用的是新探针
    with pytest.raises(AssertionError, match=r"内没有自动进入下一题"):
        _checks.auto_advance(page, 0.3, "3")


# --- 真应用：选择器、题库副本与真实切题时长 ---
def enter_group_1(page):
    page.goto(APP_INDEX.as_uri())
    page.click("#start-btn")
    page.locator("#level-grid button").first.click()


def test_real_app_smoke_state(page):
    enter_group_1(page)
    _checks.option_count_is(page, 4)
    _checks.progress_is(page, "1", "10")
    _checks.score_is(page, "0")


def test_real_app_correct_answer_scores_and_advances_after_1_5s(page):
    enter_group_1(page)
    _checks.answer_correct(page)
    _checks.score_is(page, "1")
    _checks.highlight_counts_are(page, 1, 0)
    _checks.auto_advance(page, 1.5, "2")
    _checks.progress_is(page, "2", "10")


def test_real_app_wrong_answer_highlights_and_advances_after_3s(page):
    enter_group_1(page)
    _checks.answer_wrong(page)
    _checks.score_is(page, "0")
    _checks.highlight_counts_are(page, 1, 1)
    _checks.auto_advance(page, 3, "2")


def test_real_app_answers_only_once(page):
    enter_group_1(page)
    _checks.answer_correct(page)
    _checks.click_another_unhighlighted_option(page)
    _checks.score_is(page, "1")
    _checks.highlight_counts_are(page, 1, 0)
