// 答题页（需求 F3）确定性 step 的判定逻辑——Midscene 引擎侧（TypeScript）。
//
// 只依赖 Playwright 的 Page（类型导入，运行期不 import playwright：worker 只把 @gherkai/worker-midscene 这一个包名
// 解析到自己那份）。不注册 step：注册（薄壳）在 quiz.mts，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
// 与 _checks.py 成对：选择器、题库来源、容差、消息措辞保持一致，改一侧同步另一侧。
//
// 判定约定：
// - 应用没达到期望 → 抛 DeterministicAssertion（step 记 failed），消息自带现场：期望与实际、当前题号、页面地址、选择器。
// - 用例写法错误（例如「作答后 N 秒自动进入」前面没有作答步）→ 抛普通 Error（step 记 error），与应用缺陷区分开。
// - 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。
//
// 题库：steps/_vocabulary.json 是应用源码 app/index.html 里 VOCABULARY 的副本（正确答案不显示在页面上，只能查表）。
// 自动切题时长的测法：作答点击前往页面注入一个只读探针（记录点击时刻、监听题号变化时刻），
// 之后的「作答后 N 秒自动进入第 M 题」步读探针算时长。探针不改应用行为，中间隔着耗时的 AI 步也量得准。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import type { Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";

// --- 选择器（与 _checks.py 同一份） ---
export const SEL_WORD = "#current-word";              // 生字卡上的汉字
export const SEL_OPTIONS_BOX = "#options-container";  // 选项容器
export const SEL_OPTION = ".option-btn";              // 单个拼音选项
export const SEL_OPTIONS = `${SEL_OPTIONS_BOX} ${SEL_OPTION}`;
export const SEL_SCORE = "#score-display";            // 得分
export const SEL_CURRENT_Q = "#current-q";            // 进度：当前题号
export const SEL_TOTAL_Q = "#total-q";                // 进度：总题数
export const STATE_CORRECT = "correct";               // 选项的「答对」状态（class）
export const STATE_WRONG = "wrong";                   // 选项的「答错」状态（class）

export const DEFAULT_TIMEOUT_MS = 5000;    // 页面判定的等待上限
export const HIGHLIGHT_TIMEOUT_MS = 500;   // 高亮状态在点击时同步写入，几百毫秒足够；答对只停留 1.5 秒，等太久会读到下一题
export const ADVANCE_TOLERANCE_MS = 400;   // 自动切题时长的容差：能区分 1.5 秒与 1 秒 / 2 秒 / 3 秒，也容得下定时器的正常延迟

export const PROBE_KEY = "__gherkaiQuizProbe";
const VOCABULARY_URL = new URL("./_vocabulary.json", import.meta.url);

// 探针：装在作答点击之前。记录选项区第一次点击的时刻（capture 阶段，先于应用自己的 onclick），
// 用 MutationObserver 记录题号第一次变化的时刻与变化后的题号。重复安装时先卸掉上一个。
// 写成真正的函数交给 page.evaluate / waitForFunction：Node 版 Playwright 对字符串只当表达式求值、不会调用并传参
// （Python 版会），所以这里不能像 _checks.py 那样用字符串。函数体在浏览器里执行，只用 DOM 与 window。
interface ProbeArgs { key: string; qSel: string; boxSel: string; optSel: string }

const probeInstall = ({ key, qSel, boxSel, optSel }: ProbeArgs): boolean => {
  const w = window as unknown as Record<string, any>;
  const q = document.querySelector(qSel);
  const box = document.querySelector(boxSel);
  if (!q || !box) return false;
  const old = w[key];
  if (old && typeof old.dispose === "function") old.dispose();
  const probe: Record<string, any> = { questionBefore: (q.textContent ?? "").trim(), clickedAt: null, advancedAt: null, questionAfter: null };
  const onClick = (e: Event) => {
    const t = e.target as Element | null;
    if (probe.clickedAt === null && t && typeof t.closest === "function" && t.closest(optSel)) {
      probe.clickedAt = performance.now();
    }
  };
  box.addEventListener("click", onClick, true);
  const obs = new MutationObserver(() => {
    const now = (q.textContent ?? "").trim();
    if (probe.advancedAt === null && now !== probe.questionBefore) {
      probe.advancedAt = performance.now();
      probe.questionAfter = now;
    }
  });
  obs.observe(q, { childList: true, characterData: true, subtree: true });
  probe.dispose = () => { obs.disconnect(); box.removeEventListener("click", onClick, true); };
  w[key] = probe;
  return true;
};

const probeRead = (key: string): Probe | null => {
  const p = (window as unknown as Record<string, any>)[key];
  if (!p) return null;
  return { questionBefore: p.questionBefore, clickedAt: p.clickedAt, advancedAt: p.advancedAt, questionAfter: p.questionAfter };
};

const probeAdvanced = (key: string): boolean => {
  const p = (window as unknown as Record<string, any>)[key];
  return !!(p && p.advancedAt !== null);
};

interface Probe {
  questionBefore: string;
  clickedAt: number | null;
  advancedAt: number | null;
  questionAfter: string | null;
}

// --- 题库 ---
let vocabularyCache: Map<string, string> | undefined;

/** 读 _vocabulary.json，返回 汉字 → 拼音。文件坏了或有重复汉字直接抛 Error（加载期 fail-loud）。 */
export function loadVocabulary(): Map<string, string> {
  if (vocabularyCache) return vocabularyCache;
  const items = JSON.parse(readFileSync(VOCABULARY_URL, "utf-8")) as Array<{ word: string; pinyin: string }>;
  const vocab = new Map<string, string>();
  for (const { word, pinyin } of items) {
    if (vocab.has(word)) throw new Error(`题库副本 _vocabulary.json 里汉字「${word}」重复`);
    vocab.set(word, pinyin);
  }
  if (vocab.size === 0) throw new Error("题库副本 _vocabulary.json 是空的");
  vocabularyCache = vocab;
  return vocab;
}

/** 单测用：题库副本文件的路径。 */
export const VOCABULARY_PATH = fileURLToPath(VOCABULARY_URL);

// --- 现场信息 ---
function where(page: Page, selector: string): string {
  return `页面 ${page.url()}，选择器 ${selector}`;
}

function isTimeout(e: unknown): boolean {
  return e instanceof Error && e.name === "TimeoutError";
}

function firstLine(e: unknown): string {
  return String((e as Error)?.message ?? e).split("\n")[0];
}

/** 读一个元素的文本给失败消息用；读不到就给占位，不让诊断本身再抛。 */
async function safeText(page: Page, selector: string): Promise<string> {
  try {
    return ((await page.locator(selector).first().textContent({ timeout: 500 })) ?? "").trim();
  } catch {
    return "<读不到>";
  }
}

async function liveQuestion(page: Page): Promise<string> {
  return safeText(page, SEL_CURRENT_Q);
}

const norm = (s: string): string => s.replace(/\s+/g, " ").trim();

/** 元素文本在 timeoutMs 内等于 expected（整段匹配、空白归一），否则 DeterministicAssertion 带期望与实际。 */
async function expectText(page: Page, selector: string, expected: string, what: string, timeoutMs: number): Promise<void> {
  try {
    await page.waitForFunction(
      ({ sel, exp }) => {
        const el = document.querySelector(sel);
        return !!el && (el.textContent ?? "").replace(/\s+/g, " ").trim() === exp;
      },
      { sel: selector, exp: norm(expected) },
      { timeout: timeoutMs },
    );
  } catch (e) {
    if (!isTimeout(e)) throw e;
    const actual = await safeText(page, selector);
    throw new DeterministicAssertion(`${what}应为 ${JSON.stringify(expected)}，实际 ${JSON.stringify(actual)}（${where(page, selector)}）`);
  }
}

/** 选择器命中的元素个数在 timeoutMs 内等于 n；超时返回 false（由调用方拼消息）。 */
async function waitForCount(page: Page, selector: string, n: number, timeoutMs: number): Promise<boolean> {
  try {
    await page.waitForFunction(
      ({ sel, n }) => document.querySelectorAll(sel).length === n,
      { sel: selector, n },
      { timeout: timeoutMs },
    );
    return true;
  } catch (e) {
    if (!isTimeout(e)) throw e;
    return false;
  }
}

async function optionTexts(page: Page): Promise<string[]> {
  return (await page.locator(SEL_OPTIONS).allTextContents()).map((t) => t.trim());
}

// --- 判定：进度、得分、选项个数 ---
/** 进度「当前题号 / 总题数」的数值。 */
export async function progressIs(page: Page, current: string, total: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await expectText(page, SEL_CURRENT_Q, current, "进度的当前题号", timeoutMs);
  await expectText(page, SEL_TOTAL_Q, total, "进度的总题数", timeoutMs);
}

/** 当前得分的数值。 */
export async function scoreIs(page: Page, score: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await expectText(page, SEL_SCORE, score, "得分", timeoutMs);
}

/** 本题的拼音选项恰好 count 个，且每个都有文字。 */
export async function optionCountIs(page: Page, count: number, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  if (!(await waitForCount(page, SEL_OPTIONS, count, timeoutMs))) {
    const texts = await optionTexts(page);
    throw new DeterministicAssertion(
      `拼音选项应有 ${count} 个，实际 ${texts.length} 个：${JSON.stringify(texts)}（第 ${await liveQuestion(page)} 题；${where(page, SEL_OPTIONS)}）`,
    );
  }
  const texts = await optionTexts(page);
  const empty = texts.map((t, i) => (t ? 0 : i + 1)).filter(Boolean);
  if (empty.length) {
    throw new DeterministicAssertion(`第 ${JSON.stringify(empty)} 个拼音选项没有文字：${JSON.stringify(texts)}（${where(page, SEL_OPTIONS)}）`);
  }
}

// --- 动作：按题库作答 ---
/** 等答题页就位（生字卡有字、选项已渲染），返回 [汉字, 选项文字列表]。 */
async function currentQuestion(page: Page, timeoutMs: number): Promise<[string, string[]]> {
  try {
    await page.locator(SEL_OPTIONS).first().waitFor({ state: "visible", timeout: timeoutMs });
    await page.waitForFunction(
      (sel) => ((document.querySelector(sel)?.textContent) ?? "").trim().length > 0,
      SEL_WORD,
      { timeout: timeoutMs },
    );
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`答题页没有就位：生字卡或拼音选项没有出现（页面 ${page.url()}，选择器 ${SEL_WORD} / ${SEL_OPTIONS}）`);
  }
  const word = ((await page.locator(SEL_WORD).textContent()) ?? "").trim();
  return [word, await optionTexts(page)];
}

function lookup(page: Page, word: string): string {
  const pinyin = loadVocabulary().get(word);
  if (pinyin === undefined) {
    throw new DeterministicAssertion(
      `生字卡上的「${word}」不在题库副本 _vocabulary.json 里：应用题库变了就同步这份副本（${where(page, SEL_WORD)}）`,
    );
  }
  return pinyin;
}

async function installProbe(page: Page): Promise<void> {
  const ok = await page.evaluate(probeInstall, { key: PROBE_KEY, qSel: SEL_CURRENT_Q, boxSel: SEL_OPTIONS_BOX, optSel: SEL_OPTION });
  if (!ok) {
    throw new DeterministicAssertion(`答题页没有就位：找不到进度或选项区（页面 ${page.url()}，选择器 ${SEL_CURRENT_Q} / ${SEL_OPTIONS_BOX}）`);
  }
}

async function clickOption(page: Page, texts: string[], index: number, timeoutMs: number): Promise<string> {
  const btn = page.locator(SEL_OPTIONS).nth(index);
  const actual = ((await btn.textContent()) ?? "").trim();
  if (actual !== texts[index]) {
    throw new DeterministicAssertion(
      `拼音选项在读取后发生了变化：第 ${index + 1} 个选项原为 ${JSON.stringify(texts[index])}，现为 ${JSON.stringify(actual)}` +
        `（第 ${await liveQuestion(page)} 题；${where(page, SEL_OPTIONS)}）`,
    );
  }
  await installProbe(page);
  try {
    await btn.click({ timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`拼音选项 ${JSON.stringify(actual)}（第 ${index + 1} 个）无法点击：${firstLine(e)}（${where(page, SEL_OPTIONS)}）`);
  }
  return actual;
}

/** 按题库查出生字卡上汉字的拼音并点击那个选项。返回点击的拼音。 */
export async function answerCorrect(page: Page, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<string> {
  const [word, texts] = await currentQuestion(page, timeoutMs);
  const pinyin = lookup(page, word);
  const hits = texts.map((t, i) => (t === pinyin ? i : -1)).filter((i) => i >= 0);
  if (hits.length === 0) {
    throw new DeterministicAssertion(`「${word}」的正确拼音 ${JSON.stringify(pinyin)} 不在选项里：当前选项 ${JSON.stringify(texts)}（${where(page, SEL_OPTIONS)}）`);
  }
  if (hits.length > 1) {
    throw new DeterministicAssertion(`「${word}」的正确拼音 ${JSON.stringify(pinyin)} 在选项里出现了 ${hits.length} 次：${JSON.stringify(texts)}（${where(page, SEL_OPTIONS)}）`);
  }
  return clickOption(page, texts, hits[0], timeoutMs);
}

/** 按题库排除正确拼音，点击第一个错误选项。返回点击的拼音。 */
export async function answerWrong(page: Page, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<string> {
  const [word, texts] = await currentQuestion(page, timeoutMs);
  const pinyin = lookup(page, word);
  const wrong = texts.map((t, i) => (t !== pinyin ? i : -1)).filter((i) => i >= 0);
  if (wrong.length === 0) {
    throw new DeterministicAssertion(`选项里没有「${word}」（${JSON.stringify(pinyin)}）以外的错误拼音：当前选项 ${JSON.stringify(texts)}（${where(page, SEL_OPTIONS)}）`);
  }
  return clickOption(page, texts, wrong[0], timeoutMs);
}

/** 作答之后再点一个没有高亮的选项（验证一题只答一次）。返回点击的拼音。
 *  要紧跟在作答步之后：答对只停留 1.5 秒，中间隔着耗时的 AI 步就会点到下一题上。 */
export async function clickAnotherUnhighlightedOption(page: Page, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<string> {
  const highlighted = page.locator(`${SEL_OPTIONS}.${STATE_CORRECT}, ${SEL_OPTIONS}.${STATE_WRONG}`);
  if ((await highlighted.count()) === 0) {
    throw new DeterministicAssertion(
      `没有已作答的高亮选项（当前第 ${await liveQuestion(page)} 题）：要么作答后选项没有进入答对/答错状态，` +
        `要么已经自动切到下一题——这一步要紧跟在作答步之后，中间不能隔着耗时的 AI 步（${where(page, SEL_OPTIONS)}）`,
    );
  }
  const candidates = page.locator(`${SEL_OPTIONS}:not(.${STATE_CORRECT}):not(.${STATE_WRONG})`);
  if ((await candidates.count()) === 0) {
    throw new DeterministicAssertion(`所有拼音选项都处于高亮状态，没有可再点的选项（${where(page, SEL_OPTIONS)}）`);
  }
  const btn = candidates.first();
  const text = ((await btn.textContent()) ?? "").trim();
  try {
    await btn.click({ timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`拼音选项 ${JSON.stringify(text)} 无法点击：${firstLine(e)}（${where(page, SEL_OPTIONS)}）`);
  }
  return text;
}

// --- 判定：作答后的高亮状态与自动切题 ---
/** 处于答对状态的选项 correct 个、答错状态的选项 wrong 个。 */
export async function highlightCountsAre(page: Page, correct: number, wrong: number, timeoutMs = HIGHLIGHT_TIMEOUT_MS): Promise<void> {
  const selCorrect = `${SEL_OPTIONS}.${STATE_CORRECT}`;
  const selWrong = `${SEL_OPTIONS}.${STATE_WRONG}`;
  const okCorrect = await waitForCount(page, selCorrect, correct, timeoutMs);
  const okWrong = okCorrect && (await waitForCount(page, selWrong, wrong, timeoutMs));
  if (!okCorrect || !okWrong) {
    const actualCorrect = await page.locator(selCorrect).count();
    const actualWrong = await page.locator(selWrong).count();
    throw new DeterministicAssertion(
      `处于答对状态的选项应有 ${correct} 个、答错状态的应有 ${wrong} 个，实际答对 ${actualCorrect} 个、答错 ${actualWrong} 个` +
        `（第 ${await liveQuestion(page)} 题；${where(page, SEL_OPTIONS)}）`,
    );
  }
}

/** 作答后自动进入第 question 题，且从点击到切题的时长与 seconds 秒相差不超过 toleranceMs。返回实测时长（秒）。
 *  读的是作答步装进页面的探针；这一步之前必须有 answerCorrect / answerWrong，否则是用例写法错误（普通 Error）。 */
export async function autoAdvance(page: Page, seconds: number, question: string, toleranceMs = ADVANCE_TOLERANCE_MS): Promise<number> {
  const expectedMs = seconds * 1000;
  let probe = await page.evaluate(probeRead, PROBE_KEY);
  if (probe === null) {
    throw new Error(
      `没有作答记录：「作答后 N 秒自动进入第 M 题」要用在「选择当前生字的正确拼音」或「选择一个错误的拼音」之后（页面 ${page.url()}）`,
    );
  }
  if (probe.clickedAt === null) {
    throw new Error(`作答的点击没有被记录到：作答步点的不是拼音选项，或页面在作答后被重新加载（页面 ${page.url()}）`);
  }
  if (probe.advancedAt === null) {
    try {
      await page.waitForFunction(probeAdvanced, PROBE_KEY, { timeout: expectedMs + toleranceMs + 500 });
    } catch (e) {
      if (!isTimeout(e)) throw e;
      throw new DeterministicAssertion(
        `作答后 ${seconds} 秒（容差 ±${toleranceMs / 1000} 秒）内没有自动进入下一题，仍在第 ${await liveQuestion(page)} 题` +
          `（页面 ${page.url()}，选择器 ${SEL_CURRENT_Q}）`,
      );
    }
    probe = (await page.evaluate(probeRead, PROBE_KEY)) as Probe;
  }
  const delayMs = (probe.advancedAt as number) - (probe.clickedAt as number);
  if (Math.abs(delayMs - expectedMs) > toleranceMs) {
    throw new DeterministicAssertion(
      `作答后自动进入下一题用了 ${(delayMs / 1000).toFixed(2)} 秒，期望 ${seconds} 秒（容差 ±${toleranceMs / 1000} 秒）` +
        `（页面 ${page.url()}，选择器 ${SEL_CURRENT_Q}）`,
    );
  }
  if (probe.questionAfter !== question) {
    throw new DeterministicAssertion(
      `作答后自动进入的是第 ${probe.questionAfter} 题，期望第 ${question} 题（现在显示第 ${await liveQuestion(page)} 题；` +
        `页面 ${page.url()}，选择器 ${SEL_CURRENT_Q}）`,
    );
  }
  return delayMs / 1000;
}
