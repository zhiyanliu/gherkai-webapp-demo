// 选关页（需求 F2）确定性 step 的判定逻辑——Midscene 引擎侧（TypeScript）。
//
// 只依赖 Playwright 的 Page（类型导入，运行期不 import playwright：worker 只把 @gherkai/worker-midscene 这一个包名
// 解析到自己那份）。不注册 step：注册（薄壳）在 level_select.mts，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
// 与 _level_select.py 成对：选择器、判定口径、消息措辞保持一致，改一侧同步另一侧。
//
// 判定约定（与 _checks.mts 同一套）：
// - 应用没达到期望 → 抛 DeterministicAssertion（step 记 failed），消息自带现场：期望与实际、当前显示的页面、页面地址、选择器。
// - 用例写法错误（例如关卡名模板里没有字母 N）→ 抛普通 Error（step 记 error），与应用缺陷区分开。
// - 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。
//
// 为什么每条判定都先等「选关页已显示」：应用四个页面的节点始终都在 DOM 里，只靠 hidden 切换显示；
// 关卡按钮在启动时就已渲染。不先判页面可见，「关卡按钮有 8 个」在主页上也会通过。
// 为什么按钮文案读 innerText 而不是 textContent：关卡名与副标题是两个块级元素，textContent 会把它们
// 黏成「第 1 组10 个生字」，innerText 才是用户看到的两行；比较前把所有空白折成一个空格。
import type { Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";

// --- 选择器（与 _level_select.py 同一份） ---
export const SEL_LEVEL_SCREEN = "#level-screen";        // 选关页整块
export const SEL_LEVEL_TITLE = "#level-screen h2";      // 选关页标题
export const SEL_LEVEL_BUTTONS = "#level-grid button";  // 关卡按钮
export const SEL_ANY_BUTTON = "button";                 // 「页面上有 X 按钮」查的是任何可见按钮
// 四个页面的节点，只用于失败消息里说「当前显示的是哪一页」
export const SCREENS: Array<[string, string]> = [
  ["主页", "#home-screen"], ["选关页", "#level-screen"], ["答题页", "#game-screen"], ["结算页", "#result-screen"],
];

export const DEFAULT_TIMEOUT_MS = 5000;     // 页面判定的等待上限（页面切换动画 0.5 秒，5 秒足够）
export const LEVEL_NAME_PLACEHOLDER = "N";  // 关卡名模板里代入序号的字母：「第 N 组」→「第 1 组」「第 2 组」…

/** 把所有空白（含换行）折成一个空格并去首尾：innerText 的两行 → 「第 1 组 10 个生字」。 */
export const normalize = (s: string): string => s.replace(/\s+/g, " ").trim();

// 浏览器里执行的判定。写成真正的函数交给 page.evaluate / waitForFunction：Node 版 Playwright 对字符串只当表达式求值、
// 不会调用并传参。函数体在浏览器里执行，只用 DOM。
// 用 innerText 而非 accessible name：开始按钮里有一张 alt 文字的图片，accessible name 会带上它。
const visibleButtonsWithText = ({ sel, text }: { sel: string; text: string }): number =>
  Array.from(document.querySelectorAll<HTMLElement>(sel))
    .filter((b) => b.getClientRects().length > 0 && b.innerText.replace(/\s+/g, " ").trim() === text).length;

const visibleButtonTexts = (sel: string): string[] =>
  Array.from(document.querySelectorAll<HTMLElement>(sel))
    .filter((b) => b.getClientRects().length > 0)
    .map((b) => b.innerText.replace(/\s+/g, " ").trim());

const visibleScreens = (screens: Array<[string, string]>): string[] =>
  screens
    .filter(([, sel]) => { const el = document.querySelector(sel); return !!el && el.getClientRects().length > 0; })
    .map(([name]) => name);

const elementTextEquals = ({ sel, exp }: { sel: string; exp: string }): boolean => {
  const el = document.querySelector(sel);
  return !!el && (el.textContent ?? "").replace(/\s+/g, " ").trim() === exp;
};

const elementCountEquals = ({ sel, n }: { sel: string; n: number }): boolean => document.querySelectorAll(sel).length === n;

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

async function visibleButtonTextList(page: Page): Promise<string[]> {
  try {
    return await page.evaluate(visibleButtonTexts, SEL_ANY_BUTTON);
  } catch {
    return ["<读不到>"];
  }
}

async function levelButtonTexts(page: Page): Promise<string[]> {
  return (await page.locator(SEL_LEVEL_BUTTONS).allInnerTexts()).map(normalize);
}

// --- 前置：选关页已显示 ---
/** 选关页在 timeoutMs 内可见，否则 DeterministicAssertion 说明当前显示的是哪一页。 */
async function waitLevelScreen(page: Page, timeoutMs: number): Promise<void> {
  try {
    await page.locator(SEL_LEVEL_SCREEN).waitFor({ state: "visible", timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`选关页没有显示：当前显示的是 ${await visibleScreenNames(page)}（${where(page, SEL_LEVEL_SCREEN)}）`);
  }
}

// --- 判定：标题、按钮个数、按钮文案 ---
/** 选关页已显示，且标题文字恰为 title（空白归一）。 */
export async function levelTitleIs(page: Page, title: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await waitLevelScreen(page, timeoutMs);
  try {
    await page.waitForFunction(elementTextEquals, { sel: SEL_LEVEL_TITLE, exp: normalize(title) }, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(
      `选关页标题应为 ${JSON.stringify(title)}，实际 ${JSON.stringify(await safeText(page, SEL_LEVEL_TITLE))}（${where(page, SEL_LEVEL_TITLE)}）`,
    );
  }
}

/** 选关页已显示，且关卡按钮恰好 count 个。 */
export async function levelButtonCountIs(page: Page, count: number, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  await waitLevelScreen(page, timeoutMs);
  try {
    await page.waitForFunction(elementCountEquals, { sel: SEL_LEVEL_BUTTONS, n: count }, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    const texts = await levelButtonTexts(page);
    throw new DeterministicAssertion(
      `关卡按钮应有 ${count} 个，实际 ${texts.length} 个：${JSON.stringify(texts)}（${where(page, SEL_LEVEL_BUTTONS)}）`,
    );
  }
}

/** 第 index 个（1 起）关卡按钮的期望文案（空白归一）：模板里的 N 代入序号，再接副标题。 */
export function expectedLevelLabel(nameTemplate: string, sub: string, index: number): string {
  return normalize(`${nameTemplate.replaceAll(LEVEL_NAME_PLACEHOLDER, String(index))} ${sub}`);
}

/** 每个关卡按钮的文案恰为「关卡名 + 副标题」：第 N 个按钮的关卡名是模板里的 N 代入 N。返回实际文案列表。
 *  模板里没有字母 N 是用例写法错误（普通 Error）：那样每个按钮都会期望同一个名字。 */
export async function levelButtonsLabeled(page: Page, nameTemplate: string, sub: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<string[]> {
  if (!nameTemplate.includes(LEVEL_NAME_PLACEHOLDER)) {
    throw new Error(
      `关卡名模板 ${JSON.stringify(nameTemplate)} 里没有字母 ${LEVEL_NAME_PLACEHOLDER}：要写成「第 N 组」这样，N 会依次代入 1、2、3…`,
    );
  }
  await waitLevelScreen(page, timeoutMs);
  try {
    await page.locator(SEL_LEVEL_BUTTONS).first().waitFor({ state: "visible", timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`选关页上没有关卡按钮（${where(page, SEL_LEVEL_BUTTONS)}）`);
  }
  const texts = await levelButtonTexts(page);
  const mismatches: string[] = [];
  texts.forEach((actual, i) => {
    const index = i + 1;
    if (actual !== expectedLevelLabel(nameTemplate, sub, index)) {
      mismatches.push(
        `第 ${index} 个应标注「${nameTemplate.replaceAll(LEVEL_NAME_PLACEHOLDER, String(index))}」与「${sub}」，实际 ${JSON.stringify(actual)}`,
      );
    }
  });
  if (mismatches.length) {
    throw new DeterministicAssertion(
      `关卡按钮的文案不符（共 ${texts.length} 个按钮，${mismatches.length} 个不符）：${mismatches.join("；")}（${where(page, SEL_LEVEL_BUTTONS)}）`,
    );
  }
  return texts;
}

// --- 判定：页面上有某个按钮 ---
/** 页面上至少有一个可见的按钮，其文字（空白归一）恰为 text。整段相等，「返回」不算命中「返回主页」。 */
export async function hasVisibleButton(page: Page, text: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  const expected = normalize(text);
  try {
    // 返回命中个数，0 为假值：waitForFunction 等到它非 0（函数体在浏览器里执行，不能引用 Node 侧的别的函数）
    await page.waitForFunction(visibleButtonsWithText, { sel: SEL_ANY_BUTTON, text: expected }, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(
      `页面上没有文字为 ${JSON.stringify(expected)} 的可见按钮，当前可见的按钮：${JSON.stringify(await visibleButtonTextList(page))}` +
        `（当前显示的是 ${await visibleScreenNames(page)}；${where(page, SEL_ANY_BUTTON)}）`,
    );
  }
}
