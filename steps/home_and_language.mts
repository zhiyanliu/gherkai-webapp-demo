// 主页与界面语言（需求 F1、F5）的确定性 step——Midscene 引擎侧注册（薄壳）。
//
// 判定逻辑在 _home_and_language.mts；与 home_and_language.py 成对：模式语义、description、example 同文，只是方言不同
// （TS 具名组 (?<name>…)，Python 具名组 (?P<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
// `gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/home-and-language.feature` 看标注。
//
// 文件名用下划线（home_and_language）而不是 feature 的连字符（home-and-language）：Python 模块名不能带连字符，两侧同名成对。
// 模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与内建的 `页面地址(?:精确)?匹配 "…"`、
// level_select.mts 里的 `选关页的标题是 "…"` / `页面上有 "…" 按钮`、quiz.mts 里的 `进度显示 "…"` 重叠。
// 「刷新页面」没有参数，两端加锚定（^…$）：只命中整句恰为「刷新页面」的动作步，不会顺带命中提到刷新的 AI 断言。
// 只从包名 @gherkai/worker-midscene 导入（worker 把它解析到自己那份）。
import { deterministic } from "@gherkai/worker-midscene";
import { langToggleShows, pageTitleIs, queryParamIs, reloadPage } from "./_home_and_language.mts";

deterministic(
  '页面标题是 "(?<title>[^"]+)"',
  ({ page }, { title }) => pageTitleIs(page, title),
  { description: "断言页面标题（浏览器标签上的文字）恰为给定内容（精确判定，不走 AI）", example: 'Then 页面标题是 "识字大挑战 - 二年级上册"' },
);

deterministic(
  '语言切换按钮显示 "(?<label>[^"]+)"',
  ({ page }, { label }) => langToggleShows(page, label),
  { description: "断言右上角的语言切换按钮可见，且按钮上的文字恰为给定内容（精确判定，不走 AI）", example: 'Then 语言切换按钮显示 "EN"' },
);

deterministic(
  '地址栏的 "(?<name>[^"]+)" 参数是 "(?<value>[^"]+)"',
  ({ page }, { name, value }) => queryParamIs(page, name, value),
  { description: "断言地址栏（当前页面地址）里给定查询参数的取值恰为给定内容（精确判定，不走 AI）", example: 'Then 地址栏的 "lang" 参数是 "en"' },
);

deterministic(
  "^刷新页面$",
  async ({ page }) => { await reloadPage(page); },
  { description: "重新加载当前页面（地址不变，等到加载完成；不走 AI）", example: "When 刷新页面" },
);
