"""主页与界面语言（需求 F1、F5）的确定性 step——Nova Act 引擎侧注册（薄壳）。

判定逻辑在 _home_and_language.py；与 home_and_language.mts 成对：模式语义、description、example 同文，只是方言不同
（Python 具名组 (?P<name>…)，TS 具名组 (?<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
`gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/home-and-language.feature` 看标注。

文件名用下划线（home_and_language）而不是 feature 的连字符（home-and-language）：Python 模块名不能带连字符，
Midscene 侧同名成对。

模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与内建的 `页面地址(?:精确)?匹配 "…"`、
level_select.py 里的 `选关页的标题是 "…"` / `页面上有 "…" 按钮`、quiz.py 里的 `进度显示 "…"` 重叠。
「刷新页面」没有参数，两端加锚定（^…$）：只命中整句恰为「刷新页面」的动作步，不会顺带命中提到刷新的 AI 断言。
handler 必须是同步函数（本引擎的约定）。
"""
from __future__ import annotations

from gherkai_worker_novaact.deterministic import deterministic

from . import _home_and_language as hl


@deterministic(r'页面标题是 "(?P<title>[^"]+)"',
               description="断言页面标题（浏览器标签上的文字）恰为给定内容（精确判定，不走 AI）",
               example='Then 页面标题是 "识字大挑战 - 二年级上册"')
def page_title_is(ctx, title: str) -> None:
    hl.page_title_is(ctx.page, title)


@deterministic(r'语言切换按钮显示 "(?P<label>[^"]+)"',
               description="断言右上角的语言切换按钮可见，且按钮上的文字恰为给定内容（精确判定，不走 AI）",
               example='Then 语言切换按钮显示 "EN"')
def lang_toggle_shows(ctx, label: str) -> None:
    hl.lang_toggle_shows(ctx.page, label)


@deterministic(r'地址栏的 "(?P<name>[^"]+)" 参数是 "(?P<value>[^"]+)"',
               description="断言地址栏（当前页面地址）里给定查询参数的取值恰为给定内容（精确判定，不走 AI）",
               example='Then 地址栏的 "lang" 参数是 "en"')
def query_param_is(ctx, name: str, value: str) -> None:
    hl.query_param_is(ctx.page, name, value)


@deterministic(r'^刷新页面$',
               description="重新加载当前页面（地址不变，等到加载完成；不走 AI）",
               example='When 刷新页面')
def reload_page(ctx) -> None:
    hl.reload_page(ctx.page)
