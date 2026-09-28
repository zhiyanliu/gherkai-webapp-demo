"""答题页（需求 F3）的确定性 step——Nova Act 引擎侧注册（薄壳）。

判定逻辑在 _checks.py；与 quiz.mts 成对：模式语义、description、example 同文，只是方言不同
（Python 具名组 (?P<name>…)，TS 具名组 (?<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
`gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/quiz.feature` 看标注。

模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与内建的 `页面地址(?:精确)?匹配 "…"` 重叠。
handler 必须是同步函数（本引擎的约定）。
"""
from __future__ import annotations

from gherkai_worker_novaact.deterministic import deterministic

from . import _checks


@deterministic(r'进度显示 "(?P<current>\d+) / (?P<total>\d+)"',
               description="断言进度「当前题号 / 总题数」的数值（精确判定，不走 AI）",
               example='Then 进度显示 "1 / 10"')
def progress_is(ctx, current: str, total: str) -> None:
    _checks.progress_is(ctx.page, current, total)


@deterministic(r'得分为 "(?P<score>\d+)"',
               description="断言当前得分的数值（精确判定，不走 AI）",
               example='Then 得分为 "0"')
def score_is(ctx, score: str) -> None:
    _checks.score_is(ctx.page, score)


@deterministic(r'拼音选项有 "(?P<count>\d+)" 个',
               description="断言本题拼音选项的个数，且每个选项都有文字（精确判定，不走 AI）",
               example='Then 拼音选项有 "4" 个')
def option_count_is(ctx, count: str) -> None:
    _checks.option_count_is(ctx.page, int(count))


@deterministic(r'选择当前生字的正确拼音',
               description="按题库查出生字卡上汉字的拼音并点击那个选项（正确答案不在页面上，查 steps/_vocabulary.json；不走 AI）",
               example='When 选择当前生字的正确拼音')
def answer_correct(ctx) -> None:
    _checks.answer_correct(ctx.page)


@deterministic(r'选择一个错误的拼音',
               description="按题库排除生字卡上汉字的正确拼音，点击第一个错误选项（不走 AI）",
               example='When 选择一个错误的拼音')
def answer_wrong(ctx) -> None:
    _checks.answer_wrong(ctx.page)


@deterministic(r'作答后立刻再点其它选项，得分与高亮都不变',
               description="答对当前题后在切题前立刻再点一个未高亮的选项，断言仍在同一题、得分只加 1、只有一个答对高亮（一题只答一次；不走 AI）",
               example='Then 作答后立刻再点其它选项，得分与高亮都不变')
def answer_then_reclick_is_ignored(ctx) -> None:
    _checks.answer_then_reclick_is_ignored(ctx.page)


@deterministic(r'处于答对状态的选项有 "(?P<correct>\d+)" 个[，,]\s*处于答错状态的选项有 "(?P<wrong>\d+)" 个',
               description="断言处于答对状态、答错状态的选项各有几个（精确判定，不走 AI）",
               example='Then 处于答对状态的选项有 "1" 个，处于答错状态的选项有 "0" 个')
def highlight_counts_are(ctx, correct: str, wrong: str) -> None:
    _checks.highlight_counts_are(ctx.page, int(correct), int(wrong))


@deterministic(r'作答后 "(?P<seconds>\d+(?:\.\d+)?)" 秒自动进入第 "(?P<question>\d+)" 题',
               description="断言作答后自动进入指定题号，且从点击到切题的时长与给定秒数相差不超过 0.4 秒；要用在作答步之后（精确判定，不走 AI）",
               example='Then 作答后 "1.5" 秒自动进入第 "2" 题')
def auto_advance(ctx, seconds: str, question: str) -> None:
    _checks.auto_advance(ctx.page, float(seconds), question)
