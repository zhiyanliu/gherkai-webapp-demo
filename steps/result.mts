// 结算页（需求 F4）的确定性 step——Midscene 引擎侧注册（薄壳）。
//
// 判定逻辑在 _result.mts（连答多题复用 _checks.mts 里按题库作答的逻辑）；与 result.py 成对：模式语义、description、example 同文，
// 只是方言不同（TS 具名组 (?<name>…)，Python 具名组 (?P<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
// `gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/result.feature` 看标注。
//
// 模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与已注册的模式重叠。匹配是子串搜索，所以：
// - 最终得分写成「结算页的最终得分是 "N"」而不是「最终得分为 "N"」：后者含子串 `得分为 "N"`，会同时命中 quiz.mts 的
//   `得分为 "(?<score>\d+)"`，一步命中两条模式直接记 error。
// - 「结算页的标题是 "…"」与 level_select.mts 的 `选关页的标题是 "…"`、home_and_language.mts 的 `页面标题是 "…"` 互不包含。
// - 「依次答对全部 "N" 题」「依次答错全部 "N" 题」「依次答对 "N" 题，再答错 "M" 题」三条互不包含（前两条在「答对/答错」后紧跟「全部」，
//   第三条紧跟引号）。
// 只从包名 @gherkai/worker-midscene 导入（worker 把它解析到自己那份）。
import { deterministic } from "@gherkai/worker-midscene";
import {
  answerAllCorrect,
  answerAllWrong,
  answerInSequence,
  finalScoreIs,
  resultMessageIs,
  resultTitleIs,
} from "./_result.mts";

deterministic(
  '依次答对全部 "(?<total>\\d+)" 题',
  async ({ page }, { total }) => { await answerAllCorrect(page, Number(total)); },
  {
    description: "从第 1 题起按题库依次答对本组全部题目（先核对进度里的总题数），每题作答后等自动切题再答下一题，答完最后一题等到进入结算页（不走 AI）",
    example: 'When 依次答对全部 "10" 题',
  },
);

deterministic(
  '依次答错全部 "(?<total>\\d+)" 题',
  async ({ page }, { total }) => { await answerAllWrong(page, Number(total)); },
  {
    description: "从第 1 题起按题库依次答错本组全部题目（先核对进度里的总题数），每题作答后等自动切题再答下一题，答完最后一题等到进入结算页（不走 AI）",
    example: 'When 依次答错全部 "10" 题',
  },
);

deterministic(
  '依次答对 "(?<correct>\\d+)" 题[，,]\\s*再答错 "(?<wrong>\\d+)" 题',
  async ({ page }, { correct, wrong }) => { await answerInSequence(page, Number(correct), Number(wrong)); },
  {
    description: "从当前题起按题库先依次答对给定题数、再依次答错给定题数，每题作答后等自动切题再答下一题；两数之和等于本组题数时答完进入结算页（不走 AI）",
    example: 'When 依次答对 "8" 题，再答错 "2" 题',
  },
);

deterministic(
  '结算页的标题是 "(?<title>[^"]+)"',
  ({ page }, { title }) => resultTitleIs(page, title),
  { description: "断言结算页已显示，且标题文字恰为给定内容（精确判定，不走 AI）", example: 'Then 结算页的标题是 "挑战完成！"' },
);

deterministic(
  '结算页的最终得分是 "(?<score>\\d+)"',
  ({ page }, { score }) => finalScoreIs(page, score),
  { description: "断言结算页已显示，且最终得分的数值恰为给定值（精确判定，不走 AI）", example: 'Then 结算页的最终得分是 "10"' },
);

deterministic(
  '结算页的评语是 "(?<message>[^"]+)"',
  ({ page }, { message }) => resultMessageIs(page, message),
  { description: "断言结算页已显示，且评语文字恰为给定内容（含表情符号；精确判定，不走 AI）", example: 'Then 结算页的评语是 "太厉害了！全对！🌟"' },
);
