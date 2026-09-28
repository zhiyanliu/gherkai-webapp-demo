// 答题页（需求 F3）的确定性 step——Midscene 引擎侧注册（薄壳）。
//
// 判定逻辑在 _checks.mts；与 quiz.py 成对：模式语义、description、example 同文，只是方言不同
// （TS 具名组 (?<name>…)，Python 具名组 (?P<name>…)）。改一侧同步另一侧，然后两个引擎各查一遍
// `gherkai list-deterministic --engine <引擎>`，再用 `gherkai plan features/quiz.feature` 看标注。
//
// 模式写窄（带引号参数与特征词），避免误伤本该走 AI 的步、也避免与内建的 `页面地址(?:精确)?匹配 "…"` 重叠。
// 只从包名 @gherkai/worker-midscene 导入（worker 把它解析到自己那份）。
import { deterministic } from "@gherkai/worker-midscene";
import {
  answerCorrect,
  answerWrong,
  autoAdvance,
  clickAnotherUnhighlightedOption,
  highlightCountsAre,
  optionCountIs,
  progressIs,
  scoreIs,
} from "./_checks.mts";

deterministic(
  '进度显示 "(?<current>\\d+) / (?<total>\\d+)"',
  ({ page }, { current, total }) => progressIs(page, current, total),
  { description: "断言进度「当前题号 / 总题数」的数值（精确判定，不走 AI）", example: 'Then 进度显示 "1 / 10"' },
);

deterministic(
  '得分为 "(?<score>\\d+)"',
  ({ page }, { score }) => scoreIs(page, score),
  { description: "断言当前得分的数值（精确判定，不走 AI）", example: 'Then 得分为 "0"' },
);

deterministic(
  '拼音选项有 "(?<count>\\d+)" 个',
  ({ page }, { count }) => optionCountIs(page, Number(count)),
  { description: "断言本题拼音选项的个数，且每个选项都有文字（精确判定，不走 AI）", example: 'Then 拼音选项有 "4" 个' },
);

deterministic(
  "选择当前生字的正确拼音",
  async ({ page }) => { await answerCorrect(page); },
  {
    description: "按题库查出生字卡上汉字的拼音并点击那个选项（正确答案不在页面上，查 steps/_vocabulary.json；不走 AI）",
    example: "When 选择当前生字的正确拼音",
  },
);

deterministic(
  "选择一个错误的拼音",
  async ({ page }) => { await answerWrong(page); },
  { description: "按题库排除生字卡上汉字的正确拼音，点击第一个错误选项（不走 AI）", example: "When 选择一个错误的拼音" },
);

deterministic(
  "再点一个尚未高亮的拼音选项",
  async ({ page }) => { await clickAnotherUnhighlightedOption(page); },
  {
    description: "作答之后再点一个没有高亮的选项，用于验证一题只答一次；要紧跟在作答步之后（不走 AI）",
    example: "When 再点一个尚未高亮的拼音选项",
  },
);

deterministic(
  '处于答对状态的选项有 "(?<correct>\\d+)" 个[，,]\\s*处于答错状态的选项有 "(?<wrong>\\d+)" 个',
  ({ page }, { correct, wrong }) => highlightCountsAre(page, Number(correct), Number(wrong)),
  {
    description: "断言处于答对状态、答错状态的选项各有几个（精确判定，不走 AI）",
    example: 'Then 处于答对状态的选项有 "1" 个，处于答错状态的选项有 "0" 个',
  },
);

deterministic(
  '作答后 "(?<seconds>\\d+(?:\\.\\d+)?)" 秒自动进入第 "(?<question>\\d+)" 题',
  async ({ page }, { seconds, question }) => { await autoAdvance(page, Number(seconds), question); },
  {
    description: "断言作答后自动进入指定题号，且从点击到切题的时长与给定秒数相差不超过 0.4 秒；要用在作答步之后（精确判定，不走 AI）",
    example: 'Then 作答后 "1.5" 秒自动进入第 "2" 题',
  },
);
