"""选关页（需求 F2）的确定性 step——Nova Act 引擎侧注册（薄壳）。

判定逻辑在 _level_select.py；与 level_select.mts 成对：模式语义、description、example 同文，只是方言不同
（Python 具名组 (?P<name>…)，TS 具名组 (?<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
`gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/level-select.feature` 看标注。

文件名用下划线（level_select）而不是 feature 的连字符（level-select）：Python 模块名不能带连字符，
Midscene 侧同名成对。

模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与内建的 `页面地址(?:精确)?匹配 "…"`
和 quiz.py 里的 `拼音选项有 "…" 个` 重叠。handler 必须是同步函数（本引擎的约定）。
"""
from __future__ import annotations

from gherkai_worker_novaact.deterministic import deterministic

from . import _level_select


@deterministic(r'选关页的标题是 "(?P<title>[^"]+)"',
               description="断言选关页已显示，且标题文字恰为给定内容（精确判定，不走 AI）",
               example='Then 选关页的标题是 "选择关卡"')
def level_title_is(ctx, title: str) -> None:
    _level_select.level_title_is(ctx.page, title)


@deterministic(r'关卡按钮有 "(?P<count>\d+)" 个',
               description="断言选关页已显示，且关卡按钮恰好有给定个数（精确判定，不走 AI）",
               example='Then 关卡按钮有 "8" 个')
def level_button_count_is(ctx, count: str) -> None:
    _level_select.level_button_count_is(ctx.page, int(count))


@deterministic(r'关卡按钮依次标注 "(?P<name>[^"]+)" 与 "(?P<sub>[^"]+)"',
               description="断言每个关卡按钮的文案恰为「关卡名 + 副标题」：关卡名模板里的字母 N 依次代入 1、2、3…（精确判定，不走 AI）",
               example='Then 关卡按钮依次标注 "第 N 组" 与 "10 个生字"')
def level_buttons_labeled(ctx, name: str, sub: str) -> None:
    _level_select.level_buttons_labeled(ctx.page, name, sub)


@deterministic(r'页面上有 "(?P<text>[^"]+)" 按钮',
               description="断言页面上有一个可见的按钮，其文字恰为给定内容（精确判定，不走 AI）",
               example='Then 页面上有 "返回主页" 按钮')
def has_visible_button(ctx, text: str) -> None:
    _level_select.has_visible_button(ctx.page, text)
