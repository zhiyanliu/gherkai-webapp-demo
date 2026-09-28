// 结算页（需求 F4）确定性 step 的判定逻辑——Midscene 引擎侧（TypeScript）。
//
// 只依赖 Playwright 的 Page（类型导入，运行期不 import playwright：worker 只把 @gherkai/worker-midscene 这一个包名
// 解析到自己那份）。不注册 step：注册（薄壳）在 result.mts，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
// 与 _result.py 成对：选择器、判定口径、消息措辞保持一致，改一侧同步另一侧。
//
// 判定约定（与 _checks.mts、_level_select.mts 同一套）：
// - 应用没达到期望 → 抛 DeterministicAssertion（step 记 failed），消息自带现场：期望与实际、当前显示的页面、页面地址、选择器。
// - 用例写法错误（例如要答的题数超过本组剩余题数、「依次答对全部 N 题」没从第 1 题开始用）→ 抛普通 Error
//   （step 记 error），与应用缺陷区分开。
// - 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。
//
// 连答多题怎么做：每题复用 _checks 里按题库作答的 answerCorrect / answerWrong（查 steps/_vocabulary.json 点选项），
// 作答后等页面自动切换——进度里的题号变了（进入下一题）或结算页显示出来（答完最后一题）——再答下一题。
// 每题的等待上限是需求里的停留时长（答对 1.5 秒、答错 3 秒）加上页面判定的常规余量。这一步只保证「等到切题再答」，
// 切题时长是否精确为 1.5 秒 / 3 秒由答题页的 step（作答后 N 秒自动进入第 M 题）判，这里不重复。
// 每次作答前核对进度里的题号就是期望的那一题：应用跳题、或答完最后一题没进结算页而是出了第 11 题，都在这里报出来，
// 不留给后面的结算页判定去猜。
//
// 为什么结算页的每条判定都先等「结算页已显示」：四个页面的节点始终都在 DOM 里，只靠 hidden 切换显示；
// 最终得分与评语的节点带着上一局（或 HTML 里的占位）文字，不先判页面可见会在别的页面上误判通过。
import type { Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";
import { answerCorrect, answerWrong, SEL_CURRENT_Q, SEL_GAME_SCREEN, SEL_TOTAL_Q, SEL_WORD } from "./_checks.mts";

// --- 选择器（与 _result.py 同一份） ---
export const SEL_RESULT_SCREEN = "#result-screen";    // 结算页整块
export const SEL_RESULT_TITLE = "#result-screen h2";  // 结算页标题
export const SEL_FINAL_SCORE = "#final-score";        // 最终得分
export const SEL_RESULT_MSG = "#result-msg";          // 评语
// 四个页面的节点，只用于失败消息里说「当前显示的是哪一页」
export const SCREENS: Array<[string, string]> = [
  ["主页", "#home-screen"], ["选关页", "#level-screen"], ["答题页", "#game-screen"], ["结算页", "#result-screen"],
];

export const DEFAULT_TIMEOUT_MS = 5000;   // 页面判定的等待上限（页面切换动画 0.5 秒，5 秒足够）
export const CORRECT_ADVANCE_MS = 1500;   // 需求 F3：答对后停留 1.5 秒再切题
export const WRONG_ADVANCE_MS = 3000;     // 需求 F3：答错后停留 3 秒再切题

export type Kind = "correct" | "wrong";
export type Outcome = "next" | "result";   // 作答后进入了下一题 / 进入了结算页

export interface AnswerRecord {
  question: number;
  word: string;
  pinyin: string;
  kind: Kind;
  outcome: Outcome;
}

/** 把所有空白（含换行）折成一个空格并去首尾。 */
export const normalize = (s: string): string => s.replace(/\s+/g, " ").trim();

// 浏览器里执行的判定。写成真正的函数交给 page.evaluate / waitForFunction：Node 版 Playwright 对字符串只当表达式求值、
// 不会调用并传参。函数体在浏览器里执行，只用 DOM。
// 作答后等切换：结算页有布局盒 → 'result'；题号不再是作答前的值 → 'next'；都没有 → null（waitForFunction 继续等）。
const advanceOutcome = ({ qSel, before, resultSel }: { qSel: string; before: string; resultSel: string }): Outcome | null => {
  const r = document.querySelector(resultSel);
  if (r && r.getClientRects().length > 0) return "result";
  const q = document.querySelector(qSel);
  if (q && (q.textContent ?? "").trim() !== before) return "next";
  return null;
};

const visibleScreens = (screens: Array<[string, string]>): string[] =>
  screens
    .filter(([, sel]) => { const el = document.querySelector(sel); return !!el && el.getClientRects().length > 0; })
    .map(([name]) => name);

const elementTextEquals = ({ sel, exp }: { sel: string; exp: string }): boolean => {
  const el = document.querySelector(sel);
  return !!el && (el.textContent ?? "").replace(/\s+/g, " ").trim() === exp;
};

// --- 现场信息 ---
function where(page: Page, selector: string): string {
  return `页面 ${page.url()}，选择器 ${selector}`;
}

function isTimeout(e: unknown): boolean {
  return e instanceof Error && e.name === "TimeoutError";
}

/** 读一个元素的文本给失败消息用；读不到就给占位，不让诊断本身再抛。 */
async function safeText(page: Page, selector: string): Promise<string> {
  try {
    return normalize((await page.locator(selector).first().textContent({ timeout: 500 })) ?? "");
  } catch {
    return "<读不到>";
  }
}

async function visibleScreenNames(page: Page): Promise<string> {
  try {
    const names = await page.evaluate(visibleScreens, SCREENS);
    return names.length ? names.join("、") : "没有任何页面";
  } catch {
    return "<读不到>";
  }
}

async function liveQuestion(page: Page): Promise<string> {
  return safeText(page, SEL_CURRENT_Q);
}

const kindLabel = (kind: Kind): string => (kind === "correct" ? "对" : "错");

// --- 前置：答题页已显示、读进度 ---
/** 答题页在 timeoutMs 内可见，否则 DeterministicAssertion 说明当前显示的是哪一页。 */
async function requireGameScreen(page: Page, timeoutMs: number): Promise<void> {
  try {
    await page.locator(SEL_GAME_SCREEN).waitFor({ state: "visible", timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(
      `答题页没有显示，无法作答：当前显示的是 ${await visibleScreenNames(page)}（${where(page, SEL_GAME_SCREEN)}）`,
    );
  }
}

/** 读进度里的当前题号与总题数（整数）；不是数字算应用没达到期望（DeterministicAssertion）。 */
async function readProgress(page: Page): Promise<[number, number]> {
  const current = await safeText(page, SEL_CURRENT_Q);
  const total = await safeText(page, SEL_TOTAL_Q);
  const cur = /^\d+$/.test(current) ? Number(current) : NaN;
  const tot = /^\d+$/.test(total) ? Number(total) : NaN;
  if (Number.isNaN(cur) || Number.isNaN(tot)) {
    throw new DeterministicAssertion(
      `进度里的当前题号与总题数应是数字，实际 ${JSON.stringify(current)} / ${JSON.stringify(total)}` +
        `（${where(page, `${SEL_CURRENT_Q} / ${SEL_TOTAL_Q}`)}）`,
    );
  }
  return [cur, tot];
}

/** 作答后等页面自动切换：返回 'next'（进入下一题）、'result'（进入结算页）；timeoutMs 内都没发生返回 null。 */
async function waitAdvance(page: Page, questionBefore: string, timeoutMs: number): Promise<Outcome | null> {
  try {
    const handle = await page.waitForFunction(
      advanceOutcome,
      { qSel: SEL_CURRENT_Q, before: questionBefore, resultSel: SEL_RESULT_SCREEN },
      { timeout: timeoutMs },
    );
    return (await handle.jsonValue()) as Outcome;
  } catch (e) {
    if (!isTimeout(e)) throw e;
    return null;
  }
}

// --- 动作：连答多题 ---
/** 从当前题起，按题库先依次答对 correct 题、再依次答错 wrong 题；每题作答后等自动切题（或进入结算页）再答下一题。
 *
 *  返回每题的记录：题号、生字、点的拼音、答对还是答错、作答后进入了下一题还是结算页。
 *  要答的题数超过本组剩余题数、或两个数都是 0，是用例写法错误（普通 Error）。
 *  应用没按需求走——作答后不切题、没答完就进结算页、跳题、答完最后一题没进结算页——都是 DeterministicAssertion，消息带题号与现场。 */
export async function answerInSequence(page: Page, correct: number, wrong: number, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<AnswerRecord[]> {
  const plan: Kind[] = [...Array<Kind>(correct).fill("correct"), ...Array<Kind>(wrong).fill("wrong")];
  if (plan.length === 0) throw new Error("要答的题数是 0：答对与答错的题数不能都是 0");
  await requireGameScreen(page, timeoutMs);
  const [start, total] = await readProgress(page);
  const remaining = total - start + 1;
  if (plan.length > remaining) {
    throw new Error(
      `要答 ${plan.length} 题（答对 ${correct} 题、答错 ${wrong} 题），但当前是第 ${start} 题、共 ${total} 题，` +
        `只剩 ${remaining} 题可答（页面 ${page.url()}）`,
    );
  }

  const records: AnswerRecord[] = [];
  for (let i = 0; i < plan.length; i++) {
    const kind = plan[i];
    const question = start + i;
    const live = await liveQuestion(page);
    if (live !== String(question)) {
      throw new DeterministicAssertion(
        `第 ${i + 1} 次作答前进度应显示第 ${question} 题，实际显示第 ${live} 题（已答 ${i} 题，共 ${total} 题；${where(page, SEL_CURRENT_Q)}）`,
      );
    }
    const pinyin = kind === "correct" ? await answerCorrect(page, timeoutMs) : await answerWrong(page, timeoutMs);
    const word = await safeText(page, SEL_WORD); // 作答后页面至少停留 1.5 秒，这时读到的还是本题的生字
    const delayMs = kind === "correct" ? CORRECT_ADVANCE_MS : WRONG_ADVANCE_MS;
    const waitMs = delayMs + timeoutMs;
    const outcome = await waitAdvance(page, String(question), waitMs);
    if (outcome === null) {
      throw new DeterministicAssertion(
        `答${kindLabel(kind)}第 ${question} 题（「${word}」选 ${JSON.stringify(pinyin)}）后 ${waitMs / 1000} 秒内没有自动进入下一题，` +
          `也没有进入结算页，仍显示第 ${await liveQuestion(page)} 题（共 ${total} 题；${where(page, SEL_CURRENT_Q)}）`,
      );
    }
    records.push({ question, word, pinyin, kind, outcome });
    const isLast = i === plan.length - 1;
    if (outcome === "result" && !isLast) {
      throw new DeterministicAssertion(
        `答完第 ${question} 题就进入了结算页，还有 ${plan.length - i - 1} 题没答（共 ${total} 题；${where(page, SEL_RESULT_SCREEN)}）`,
      );
    }
    if (outcome === "next" && question === total) {
      throw new DeterministicAssertion(
        `答完最后一题（第 ${total} 题）后没有进入结算页，进度显示第 ${await liveQuestion(page)} 题（${where(page, SEL_CURRENT_Q)}）`,
      );
    }
  }
  return records;
}

/** 从第 1 题起把本组 total 题全部答对（或全部答错）。先核对进度里的总题数就是 total，且当前是第 1 题。 */
async function answerAll(page: Page, kind: Kind, total: number, timeoutMs: number): Promise<AnswerRecord[]> {
  await requireGameScreen(page, timeoutMs);
  const [current, actualTotal] = await readProgress(page);
  if (actualTotal !== total) {
    throw new DeterministicAssertion(`本组应共 ${total} 题，进度显示共 ${actualTotal} 题（${where(page, SEL_TOTAL_Q)}）`);
  }
  if (current !== 1) {
    throw new Error(`「依次答${kindLabel(kind)}全部 ${total} 题」要在刚进入关卡、第 1 题时用，当前已是第 ${current} 题（页面 ${page.url()}）`);
  }
  return kind === "correct" ? answerInSequence(page, total, 0, timeoutMs) : answerInSequence(page, 0, total, timeoutMs);
}

/** 从第 1 题起依次答对本组全部 total 题，答完进入结算页。返回每题的记录。 */
export async function answerAllCorrect(page: Page, total: number, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<AnswerRecord[]> {
  return answerAll(page, "correct", total, timeoutMs);
}

/** 从第 1 题起依次答错本组全部 total 题，答完进入结算页。返回每题的记录。 */
export async function answerAllWrong(page: Page, total: number, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<AnswerRecord[]> {
  return answerAll(page, "wrong", total, timeoutMs);
}

// --- 前置：结算页已显示 ---
/** 结算页在 timeoutMs 内可见，否则 DeterministicAssertion 说明当前显示的是哪一页。 */
async function waitResultScreen(page: Page, timeoutMs: number): Promise<void> {
  try {
    await page.locator(SEL_RESULT_SCREEN).waitFor({ state: "visible", timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`结算页没有显示：当前显示的是 ${await visibleScreenNames(page)}（${where(page, SEL_RESULT_SCREEN)}）`);
  }
}

/** 结算页上某个元素的文本在 timeoutMs 内恰为 expected（空白归一、整段相等），否则 DeterministicAssertion 带期望与实际。 */
async function expectResultText(page: Page, selector: string, expected: string, what: string, timeoutMs: number): Promise<void> {
  try {
    await page.waitForFunction(elementTextEquals, { sel: selector, exp: normalize(expected) }, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(
      `${what}应为 ${JSON.stringify(expected)}，实际 ${JSON.stringify(await safeText(page, selector))}（${where(page, selector)}）`,
    );
  }
}

// --- 判定：结算页标题、最终得分、评语 ---
/** 结算页已显示，且标题文字恰为 title。 */
export async function resultTitleIs(page: Page, title: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await waitResultScreen(page, timeoutMs);
  await expectResultText(page, SEL_RESULT_TITLE, title, "结算页标题", timeoutMs);
}

/** 结算页已显示，且最终得分的数值恰为 score（整段相等，「1」不算命中「10」）。 */
export async function finalScoreIs(page: Page, score: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await waitResultScreen(page, timeoutMs);
  await expectResultText(page, SEL_FINAL_SCORE, score, "最终得分", timeoutMs);
}

/** 结算页已显示，且评语文字恰为 message（含表情符号，整段相等）。 */
export async function resultMessageIs(page: Page, message: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await waitResultScreen(page, timeoutMs);
  await expectResultText(page, SEL_RESULT_MSG, message, "评语", timeoutMs);
}
