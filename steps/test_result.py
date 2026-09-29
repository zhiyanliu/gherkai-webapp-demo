"""steps/_result.py 的本地单测（Nova Act 侧判定逻辑）。

用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 test_ 开头的文件。
两类页面：
- 合成页：set_content 造出与应用同结构的最小四页骨架（同样的 id / class、同样靠 hidden 切换显示）和一套可配置的答题流程：
  题数、切题时长（几百毫秒，让 10 题也秒级跑完）、答完第几题进结算页、作答后跳到哪一题、不切题、初始显示哪一页、
  结算页上的得分与评语。题目取自题库副本里的生字，这样 _checks 的按题库作答能照常工作。用来走通过与失败两条路。
- 真应用：file:// 打开 app/index.html（英文界面加 ?lang=en），从主页点进第 1 组，验证选择器、真实文案与真实的
  1.5 秒 / 3 秒切题节奏下连答 10 题能到结算页；再玩一次与返回主页复用 _checks 与 _level_select 里的判定；另有一条在同一个页面上
  依次走完「答完 10 题、再玩一次、再答完 10 题、返回主页」，对应 features/result.feature 里同一 @scope 串行执行的三条场景。

运行：uv sync && uv run playwright install chromium && uv run pytest
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

import _checks  # pytest 把测试所在目录放进导入路径
import _level_select
import _result

APP_INDEX = Path(__file__).resolve().parent.parent / "app" / "index.html"

# 合成页用的题目：都在题库副本里（_checks 按题库查拼音）；拼音互不相同，做干扰项不会撞上正确答案
VOCAB = [("两", "liǎng"), ("哪", "nǎ"), ("宽", "kuān"), ("顶", "dǐng"), ("肚", "dù"), ("皮", "pí"),
         ("孩", "hái"), ("跳", "tiào"), ("变", "biàn"), ("极", "jí"), ("片", "piàn"), ("傍", "bàng")]

MSG_PERFECT = "太厉害了！全对！🌟"
MSG_GOOD = "真棒！继续加油！✨"
MSG_TRY_AGAIN = "再接再厉哦！💪"


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


def result_html(*, screen: str = "game", total: int = 10, start_at: int = 1, correct_delay: int = 100, wrong_delay: int = 200,
                advance: bool = True, end_after: int | None = None, jump_to: dict[int, int] | None = None,
                final_score: int | None = None, message: str | None = None, title: str = "挑战完成！") -> str:
    """与应用同结构的最小四页骨架加可配置的答题流程。

    - screen：初始显示哪一页（home / level / game / result）。
    - total：本组题数；start_at：初始显示第几题（造「没从第 1 题开始」）。
    - correct_delay / wrong_delay：答对 / 答错后多少毫秒切题；advance=False 作答后永不切题。
    - end_after：答完第几题进结算页（缺省 total）；jump_to：{答完第 k 题: 跳到第 n 题}，造跳题。
    - final_score / message：结算页上的得分与评语（缺省按真实规则：满分 / 8 成以上 / 其余三档）。
    """
    words = [{"word": w, "pinyin": p} for w, p in VOCAB]
    cfg = {"screen": screen, "total": total, "startAt": start_at, "correctDelay": correct_delay, "wrongDelay": wrong_delay,
           "advance": advance, "endAfter": total if end_after is None else end_after,
           "jumpTo": {str(k): v for k, v in (jump_to or {}).items()}, "finalScore": final_score, "message": message}
    return f"""<!doctype html><html><head><style>.hidden {{ display: none; }}</style></head><body>
<section id="home-screen" class="hidden"><h1>识字大挑战</h1><button id="start-btn">开始挑战</button></section>
<section id="level-screen" class="hidden"><h2>选择关卡</h2><div id="level-grid"></div><button id="back-home-btn">返回主页</button></section>
<section id="game-screen" class="hidden">
  <div><span id="score-display">0</span></div>
  <div><span id="current-q">1</span> / <span id="total-q">10</span></div>
  <div><span id="current-word"></span></div>
  <div id="options-container"></div>
</section>
<section id="result-screen" class="hidden">
  <h2>{title}</h2>
  <span id="final-score">0</span>
  <p id="result-msg">太棒了！</p>
  <button id="replay-btn">
      再玩一次
  </button>
  <button id="home-btn">返回主页</button>
</section>
<script>
  const WORDS = {json.dumps(words, ensure_ascii=False)};
  const CFG = {json.dumps(cfg, ensure_ascii=False)};
  const $ = (id) => document.getElementById(id);
  let qi = CFG.startAt - 1, score = 0, answered = 0, answering = false;
  function show(name) {{
    ['home', 'level', 'game', 'result'].forEach(s => $(s + '-screen').classList.toggle('hidden', s !== name));
  }}
  function load() {{
    answering = false;
    const q = WORDS[qi];
    $('current-q').textContent = qi + 1;
    $('total-q').textContent = CFG.total;
    $('current-word').textContent = q.word;
    const box = $('options-container');
    box.innerHTML = '';
    const opts = [1, 2, 3].map(k => WORDS[(qi + k) % WORDS.length].pinyin);
    opts.splice(qi % 4, 0, q.pinyin);
    opts.forEach(opt => {{
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.textContent = opt;
      b.onclick = () => handle(b, opt, q.pinyin);
      box.appendChild(b);
    }});
  }}
  function handle(btn, selected, correct) {{
    if (answering) return;
    answering = true;
    const ok = selected === correct;
    if (ok) {{
      btn.classList.add('correct');
      score++;
      $('score-display').textContent = score;
    }} else {{
      btn.classList.add('wrong');
      document.querySelectorAll('.option-btn').forEach(b => {{ if (b.textContent === correct) b.classList.add('correct'); }});
    }}
    answered++;
    if (!CFG.advance) return;
    setTimeout(() => {{
      if (answered >= CFG.endAfter) {{ showResult(); return; }}
      const jump = CFG.jumpTo[String(answered)];
      qi = jump ? jump - 1 : qi + 1;
      load();
    }}, ok ? CFG.correctDelay : CFG.wrongDelay);
  }}
  function showResult() {{
    show('result');
    $('final-score').textContent = CFG.finalScore ?? score;
    $('result-msg').textContent = CFG.message ?? (score === CFG.total ? {json.dumps(MSG_PERFECT, ensure_ascii=False)}
      : score >= CFG.total * 0.8 ? {json.dumps(MSG_GOOD, ensure_ascii=False)} : {json.dumps(MSG_TRY_AGAIN, ensure_ascii=False)});
  }}
  $('replay-btn').onclick = () => {{ qi = 0; score = 0; answered = 0; $('score-display').textContent = 0; show('game'); load(); }};
  $('home-btn').onclick = () => show('home');
  if (CFG.screen === 'game') {{ show('game'); load(); }}
  else if (CFG.screen === 'result') {{ show('result'); $('final-score').textContent = CFG.finalScore ?? 0; $('result-msg').textContent = CFG.message ?? ''; }}
  else show(CFG.screen);
</script></body></html>"""


def load(page, **kw):
    page.set_content(result_html(**kw))


# --- 连答多题：通过 ---
def test_answer_all_correct_reaches_result_with_full_score(page):
    load(page)
    records = _result.answer_all_correct(page, 10)
    assert [r["question"] for r in records] == list(range(1, 11))
    assert all(r["kind"] == "correct" for r in records)
    assert [r["outcome"] for r in records] == ["next"] * 9 + ["result"]
    assert all(_checks.load_vocabulary()[r["word"]] == r["pinyin"] for r in records), "每题点的都该是题库里该字的拼音"
    _result.result_title_is(page, "挑战完成！")
    _result.final_score_is(page, "10")
    _result.result_message_is(page, MSG_PERFECT)


def test_answer_all_wrong_scores_zero(page):
    load(page)
    records = _result.answer_all_wrong(page, 10)
    assert len(records) == 10 and all(r["kind"] == "wrong" for r in records)
    assert all(_checks.load_vocabulary()[r["word"]] != r["pinyin"] for r in records), "每题点的都该不是正确拼音"
    _result.final_score_is(page, "0")
    _result.result_message_is(page, MSG_TRY_AGAIN)


def test_answer_8_correct_then_2_wrong(page):
    load(page)
    records = _result.answer_in_sequence(page, 8, 2)
    assert [r["kind"] for r in records] == ["correct"] * 8 + ["wrong"] * 2
    assert records[-1]["outcome"] == "result"
    _result.final_score_is(page, "8")
    _result.result_message_is(page, MSG_GOOD)


def test_sequence_waits_for_each_advance_before_next_answer(page):
    load(page, total=3, correct_delay=300)
    started = time.monotonic()
    _result.answer_all_correct(page, 3)
    assert time.monotonic() - started >= 0.9, "三题各停留 0.3 秒才切题，连答不可能快于 0.9 秒"
    _result.final_score_is(page, "3")


def test_partial_sequence_stops_mid_quiz(page):
    load(page, total=10)
    records = _result.answer_in_sequence(page, 2, 1)
    assert [r["outcome"] for r in records] == ["next"] * 3
    _checks.progress_is(page, "4", "10")
    _checks.score_is(page, "2")


# --- 连答多题：用例写法错误（RuntimeError，记 error） ---
def test_answer_all_total_mismatch_fails(page):
    load(page, total=8)
    with pytest.raises(AssertionError, match=r"本组应共 10 题，进度显示共 8 题.*#total-q"):
        _result.answer_all_correct(page, 10)


def test_answer_all_not_from_first_question_is_usage_error(page):
    load(page, start_at=3)
    with pytest.raises(RuntimeError, match=r"「依次答对全部 10 题」要在刚进入关卡、第 1 题时用，当前已是第 3 题"):
        _result.answer_all_correct(page, 10)


def test_sequence_more_than_remaining_is_usage_error(page):
    load(page, total=3)
    with pytest.raises(RuntimeError, match=r"要答 4 题（答对 3 题、答错 1 题），但当前是第 1 题、共 3 题，只剩 3 题可答"):
        _result.answer_in_sequence(page, 3, 1)


def test_sequence_of_zero_is_usage_error(page):
    load(page)
    with pytest.raises(RuntimeError, match=r"答对与答错的题数不能都是 0"):
        _result.answer_in_sequence(page, 0, 0)


# --- 连答多题：应用没达到期望（AssertionError，记 failed） ---
def test_sequence_requires_game_screen(page):
    load(page, screen="home")
    with pytest.raises(AssertionError, match=r"答题页没有显示，无法作答：当前显示的是 主页.*#game-screen"):
        _result.answer_in_sequence(page, 1, 0, timeout_ms=300)


def test_sequence_never_advances_fails(page):
    load(page, advance=False)
    with pytest.raises(AssertionError, match=r"答对第 1 题（「两」选 'liǎng'）后 1\.8 秒内没有自动进入下一题，也没有进入结算页，仍显示第 1 题（共 10 题"):
        _result.answer_in_sequence(page, 1, 0, timeout_ms=300)


def test_sequence_result_too_early_fails(page):
    load(page, total=5, end_after=2)
    with pytest.raises(AssertionError, match=r"答完第 2 题就进入了结算页，还有 1 题没答（共 5 题"):
        _result.answer_in_sequence(page, 3, 0)


def test_sequence_skipped_question_fails(page):
    load(page, jump_to={1: 3})
    with pytest.raises(AssertionError, match=r"第 2 次作答前进度应显示第 2 题，实际显示第 3 题（已答 1 题，共 10 题"):
        _result.answer_in_sequence(page, 3, 0)


def test_sequence_last_question_without_result_fails(page):
    load(page, total=2, end_after=99)
    with pytest.raises(AssertionError, match=r"答完最后一题（第 2 题）后没有进入结算页，进度显示第 3 题"):
        _result.answer_all_correct(page, 2)


# --- 结算页判定 ---
def test_result_checks_pass(page):
    load(page, screen="result", final_score=10, message=MSG_PERFECT)
    _result.result_title_is(page, "挑战完成！")
    _result.final_score_is(page, "10")
    _result.result_message_is(page, MSG_PERFECT)


def test_result_title_mismatch_fails_with_actual(page):
    load(page, screen="result", title="Challenge Complete!")
    with pytest.raises(AssertionError, match=r"结算页标题应为 '挑战完成！'，实际 'Challenge Complete!'.*#result-screen h2"):
        _result.result_title_is(page, "挑战完成！", timeout_ms=300)


def test_final_score_is_whole_text_not_substring(page):
    load(page, screen="result", final_score=10)
    with pytest.raises(AssertionError, match=r"最终得分应为 '1'，实际 '10'.*#final-score"):
        _result.final_score_is(page, "1", timeout_ms=300)


def test_result_message_mismatch_fails_with_actual(page):
    load(page, screen="result", message=MSG_GOOD)
    with pytest.raises(AssertionError, match=r"评语应为 '太厉害了！全对！🌟'，实际 '真棒！继续加油！✨'.*#result-msg"):
        _result.result_message_is(page, MSG_PERFECT, timeout_ms=300)


def test_result_checks_require_result_screen(page):
    load(page, screen="game")
    for check in (lambda: _result.result_title_is(page, "挑战完成！", timeout_ms=300),
                  lambda: _result.final_score_is(page, "0", timeout_ms=300),
                  lambda: _result.result_message_is(page, MSG_TRY_AGAIN, timeout_ms=300)):
        with pytest.raises(AssertionError, match=r"结算页没有显示：当前显示的是 答题页.*#result-screen"):
            check()


def test_result_message_waits_for_late_update(page):
    load(page, screen="result", message="")
    page.evaluate(f"setTimeout(() => document.getElementById('result-msg').textContent = {json.dumps(MSG_PERFECT)}, 200)")
    _result.result_message_is(page, MSG_PERFECT, timeout_ms=2000)


# --- 真应用：选择器、真实文案、真实切题节奏 ---
def enter_group_1(page, lang: str | None = None):
    page.goto(APP_INDEX.as_uri() + (f"?lang={lang}" if lang else ""))
    page.click("#start-btn")
    page.locator("#level-grid button").first.click()


def test_real_app_all_correct_then_replay(page):
    enter_group_1(page)
    records = _result.answer_all_correct(page, 10)
    assert records[-1]["outcome"] == "result"
    _result.result_title_is(page, "挑战完成！")
    _result.final_score_is(page, "10")
    _result.result_message_is(page, MSG_PERFECT)
    _level_select.has_visible_button(page, "再玩一次")
    _level_select.has_visible_button(page, "返回主页")
    page.click("#replay-btn")
    _checks.progress_is(page, "1", "10")
    _checks.score_is(page, "0")


def test_real_app_all_wrong_then_home(page):
    enter_group_1(page)
    _result.answer_all_wrong(page, 10)
    _result.final_score_is(page, "0")
    _result.result_message_is(page, MSG_TRY_AGAIN)
    page.click("#home-btn")
    _level_select.has_visible_button(page, "开始挑战")


def test_real_app_8_correct_2_wrong(page):
    enter_group_1(page)
    _result.answer_in_sequence(page, 8, 2)
    _result.final_score_is(page, "8")
    _result.result_message_is(page, MSG_GOOD)


def test_real_app_english_all_correct(page):
    enter_group_1(page, "en")
    _result.answer_all_correct(page, 10)
    _result.result_title_is(page, "Challenge Complete!")
    _result.final_score_is(page, "10")
    _result.result_message_is(page, "Amazing! All correct! 🌟")
    _level_select.has_visible_button(page, "Play Again")
    _level_select.has_visible_button(page, "Back to Home")


def test_real_app_finish_replay_finish_home_in_one_session(page):
    """与 features/result.feature 里 @scope:result-replay-and-home 的三条场景同一条链、同一个页面：答完 10 题到结算页 →
    再玩一次回到第 1 题、得分清零 → 再答完 10 题到结算页 → 返回主页。关键在第二次「依次答对全部 10 题」：再玩一次后进度回到
    第 1 题，这条 step「要在第 1 题时用」的前置成立，答完仍进结算页、得分仍是 10。"""
    enter_group_1(page)
    _result.answer_all_correct(page, 10)
    _result.final_score_is(page, "10")
    page.click("#replay-btn")
    _checks.progress_is(page, "1", "10")
    _checks.score_is(page, "0")
    records = _result.answer_all_correct(page, 10)
    assert [r["question"] for r in records] == list(range(1, 11))
    assert records[-1]["outcome"] == "result"
    _result.result_title_is(page, "挑战完成！")
    _result.final_score_is(page, "10")
    _result.result_message_is(page, MSG_PERFECT)
    page.click("#home-btn")
    _level_select.has_visible_button(page, "开始挑战")


def test_real_app_result_checks_fail_on_quiz_page(page):
    """答题页上最终得分与评语的节点也在 DOM 里（带占位文字），判定必须因结算页未显示而失败。"""
    enter_group_1(page)
    with pytest.raises(AssertionError, match=r"结算页没有显示：当前显示的是 答题页"):
        _result.final_score_is(page, "0", timeout_ms=800)
