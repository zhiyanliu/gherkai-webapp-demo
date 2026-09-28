// 选关页（需求 F2）的确定性 step——Midscene 引擎侧注册（薄壳）。
//
// 判定逻辑在 _level_select.mts；与 level_select.py 成对：模式语义、description、example 同文，只是方言不同
// （TS 具名组 (?<name>…)，Python 具名组 (?P<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
// `gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/level-select.feature` 看标注。
//
// 文件名用下划线（level_select）而不是 feature 的连字符（level-select）：Python 模块名不能带连字符，两侧同名成对。
// 模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与内建的 `页面地址(?:精确)?匹配 "…"`
// 和 quiz.mts 里的 `拼音选项有 "…" 个` 重叠。只从包名 @gherkai/worker-midscene 导入（worker 把它解析到自己那份）。
import { deterministic } from "@gherkai/worker-midscene";
import { hasVisibleButton, levelButtonCountIs, levelButtonsLabeled, levelTitleIs } from "./_level_select.mts";

deterministic(
  '选关页的标题是 "(?<title>[^"]+)"',
  ({ page }, { title }) => levelTitleIs(page, title),
  { description: "断言选关页已显示，且标题文字恰为给定内容（精确判定，不走 AI）", example: 'Then 选关页的标题是 "选择关卡"' },
);

deterministic(
  '关卡按钮有 "(?<count>\\d+)" 个',
  ({ page }, { count }) => levelButtonCountIs(page, Number(count)),
  { description: "断言选关页已显示，且关卡按钮恰好有给定个数（精确判定，不走 AI）", example: 'Then 关卡按钮有 "8" 个' },
);

deterministic(
  '关卡按钮依次标注 "(?<name>[^"]+)" 与 "(?<sub>[^"]+)"',
  async ({ page }, { name, sub }) => { await levelButtonsLabeled(page, name, sub); },
  {
    description: "断言每个关卡按钮的文案恰为「关卡名 + 副标题」：关卡名模板里的字母 N 依次代入 1、2、3…（精确判定，不走 AI）",
    example: 'Then 关卡按钮依次标注 "第 N 组" 与 "10 个生字"',
  },
);

deterministic(
  '页面上有 "(?<text>[^"]+)" 按钮',
  ({ page }, { text }) => hasVisibleButton(page, text),
  { description: "断言页面上有一个可见的按钮，其文字恰为给定内容（精确判定，不走 AI）", example: 'Then 页面上有 "返回主页" 按钮' },
);
