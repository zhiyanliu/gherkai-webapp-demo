"""结算页（需求 F4）的确定性 step——Nova Act 引擎侧注册（薄壳）。

判定逻辑在 _result.py（连答多题复用 _checks.py 里按题库作答的逻辑）；与 result.mts 成对：模式语义、description、example 同文，
只是方言不同（Python 具名组 (?P<name>…)，TS 具名组 (?<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
`gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/result.feature` 看标注。

模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与已注册的模式重叠。匹配是子串搜索，所以：
- 最终得分写成「结算页的最终得分是 "N"」而不是「最终得分为 "N"」：后者含子串 `得分为 "N"`，会同时命中 quiz.py 的
  `得分为 "(?P<score>\\d+)"`，一步命中两条模式直接记 error。
- 「结算页的标题是 "…"」与 level_select.py 的 `选关页的标题是 "…"`、home_and_language.py 的 `页面标题是 "…"` 互不包含。
- 「依次答对全部 "N" 题」「依次答错全部 "N" 题」「依次答对 "N" 题，再答错 "M" 题」三条互不包含（前两条在「答对/答错」后紧跟「全部」，
  第三条紧跟引号）。
handler 必须是同步函数（本引擎的约定）。
"""
from __future__ import annotations

from gherkai_worker_novaact.deterministic import deterministic

from . import _result


@deterministic(r'依次答对全部 "(?P<total>\d+)" 题',
               description="从第 1 题起按题库依次答对本组全部题目（先核对进度里的总题数），每题作答后等自动切题再答下一题，答完最后一题等到进入结算页（不走 AI）",
               example='When 依次答对全部 "10" 题')
def answer_all_correct(ctx, total: str) -> None:
    _result.answer_all_correct(ctx.page, int(total))


@deterministic(r'依次答错全部 "(?P<total>\d+)" 题',
               description="从第 1 题起按题库依次答错本组全部题目（先核对进度里的总题数），每题作答后等自动切题再答下一题，答完最后一题等到进入结算页（不走 AI）",
               example='When 依次答错全部 "10" 题')
def answer_all_wrong(ctx, total: str) -> None:
    _result.answer_all_wrong(ctx.page, int(total))


@deterministic(r'依次答对 "(?P<correct>\d+)" 题[，,]\s*再答错 "(?P<wrong>\d+)" 题',
               description="从当前题起按题库先依次答对给定题数、再依次答错给定题数，每题作答后等自动切题再答下一题；两数之和等于本组题数时答完进入结算页（不走 AI）",
               example='When 依次答对 "8" 题，再答错 "2" 题')
def answer_in_sequence(ctx, correct: str, wrong: str) -> None:
    _result.answer_in_sequence(ctx.page, int(correct), int(wrong))


@deterministic(r'结算页的标题是 "(?P<title>[^"]+)"',
               description="断言结算页已显示，且标题文字恰为给定内容（精确判定，不走 AI）",
               example='Then 结算页的标题是 "挑战完成！"')
def result_title_is(ctx, title: str) -> None:
    _result.result_title_is(ctx.page, title)


@deterministic(r'结算页的最终得分是 "(?P<score>\d+)"',
               description="断言结算页已显示，且最终得分的数值恰为给定值（精确判定，不走 AI）",
               example='Then 结算页的最终得分是 "10"')
def final_score_is(ctx, score: str) -> None:
    _result.final_score_is(ctx.page, score)


@deterministic(r'结算页的评语是 "(?P<message>[^"]+)"',
               description="断言结算页已显示，且评语文字恰为给定内容（含表情符号；精确判定，不走 AI）",
               example='Then 结算页的评语是 "太厉害了！全对！🌟"')
def result_message_is(ctx, message: str) -> None:
    _result.result_message_is(ctx.page, message)
