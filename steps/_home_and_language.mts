// 主页与界面语言（需求 F1、F5）确定性 step 的判定逻辑——Midscene 引擎侧（TypeScript）。
//
// 只依赖 Playwright 的 Page（类型导入，运行期不 import playwright：worker 只把 @gherkai/worker-midscene 这一个包名
// 解析到自己那份）。不注册 step：注册（薄壳）在 home_and_language.mts，本文件以 `_` 开头、worker 不会把它当 step 文件加载。
// 与 _home_and_language.py 成对：选择器、判定口径、消息措辞保持一致，改一侧同步另一侧。
//
// 判定约定（与 _checks.mts、_level_select.mts 同一套）：
// - 应用没达到期望 → 抛 DeterministicAssertion（step 记 failed），消息自带现场：期望与实际、页面地址、选择器。
// - 所有判定带等待与几秒的上限，不读瞬时值、不固定 sleep。
//
// 为什么页面标题与地址栏参数都在浏览器里读（document.title / location.href）：切换语言时应用用 history.replaceState
// 改地址、用 document.title 改标题，都不触发导航；在页面里轮询到条件成立为止最直接，两侧实现也一致。
// 比较前把标题与按钮文字的空白折成一个空格（浏览器标签上显示的就是折叠后的样子）；地址栏参数按 URL 解析后逐字比较，不折空白。
//
// 为什么「刷新页面」写成确定性 step：AI 引擎只能点、输入、滚动，没有「重新加载」这个动作；重新打开地址是导航不是刷新，
// 测不到「切换后写回地址栏、刷新后保持」这条需求（F5）。
import type { Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";

// --- 选择器（与 _home_and_language.py 同一份） ---
export const SEL_LANG_TOGGLE = "#lang-toggle";   // 右上角的语言切换按钮，按钮上显示切换目标语言的名字（EN / 中文）

export const DEFAULT_TIMEOUT_MS = 5000;   // 页面判定的等待上限（切换语言是同步的，5 秒足够容下 AI 点击步的收尾）
export const RELOAD_TIMEOUT_MS = 10000;   // 刷新页面的加载上限（静态页面本机毫秒级，经隧道到云端浏览器也在几秒内）

/** 把所有空白（含换行）折成一个空格并去首尾。 */
export const normalize = (s: string): string => s.replace(/\s+/g, " ").trim();

// 浏览器里执行的判定。写成真正的函数交给 page.evaluate / waitForFunction：Node 版 Playwright 对字符串只当表达式求值、
// 不会调用并传参。函数体在浏览器里执行，只用 DOM 与 location。
const titleEquals = (exp: string): boolean => document.title.replace(/\s+/g, " ").trim() === exp;

const elementTextEquals = ({ sel, exp }: { sel: string; exp: string }): boolean => {
  const el = document.querySelector(sel);
  return !!el && (el.textContent ?? "").replace(/\s+/g, " ").trim() === exp;
};

const queryParamEquals = ({ name, value }: { name: string; value: string }): boolean =>
  new URL(location.href).searchParams.get(name) === value;

const queryParam = (name: string): string | null => new URL(location.href).searchParams.get(name);

// --- 现场信息 ---
function where(page: Page, selector: string): string {
  return `页面 ${page.url()}，选择器 ${selector}`;
}

function isTimeout(e: unknown): boolean {
  return e instanceof Error && e.name === "TimeoutError";
}

/** 读页面标题给失败消息用；读不到就给占位，不让诊断本身再抛。 */
async function safeTitle(page: Page): Promise<string> {
  try {
    return normalize(await page.title());
  } catch {
    return "<读不到>";
  }
}

async function safeText(page: Page, selector: string): Promise<string> {
  try {
    return normalize((await page.locator(selector).first().textContent({ timeout: 500 })) ?? "");
  } catch {
    return "<读不到>";
  }
}

/** 读地址栏里某个参数给失败消息用：没有这个参数返回 null，读不到给占位。 */
async function safeQueryParam(page: Page, name: string): Promise<string | null> {
  try {
    return await page.evaluate(queryParam, name);
  } catch {
    return "<读不到>";
  }
}

// --- 判定：页面标题 ---
/** 页面标题（浏览器标签上的文字）在 timeoutMs 内恰为 title（空白归一、整段相等）。 */
export async function pageTitleIs(page: Page, title: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  const expected = normalize(title);
  try {
    await page.waitForFunction(titleEquals, expected, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(
      `页面标题应为 ${JSON.stringify(expected)}，实际 ${JSON.stringify(await safeTitle(page))}（页面 ${page.url()}）`,
    );
  }
}

// --- 判定：语言切换按钮 ---
/** 语言切换按钮可见，且按钮上的文字在 timeoutMs 内恰为 label（空白归一、整段相等，「E」不算命中「EN」）。 */
export async function langToggleShows(page: Page, label: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  const expected = normalize(label);
  try {
    await page.locator(SEL_LANG_TOGGLE).waitFor({ state: "visible", timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`语言切换按钮没有显示（${where(page, SEL_LANG_TOGGLE)}）`);
  }
  try {
    await page.waitForFunction(elementTextEquals, { sel: SEL_LANG_TOGGLE, exp: expected }, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(
      `语言切换按钮应显示 ${JSON.stringify(expected)}，实际 ${JSON.stringify(await safeText(page, SEL_LANG_TOGGLE))}（${where(page, SEL_LANG_TOGGLE)}）`,
    );
  }
}

// --- 判定：地址栏参数 ---
/** 地址栏（当前页面地址）里查询参数 name 的取值在 timeoutMs 内恰为 value（逐字相等）。
 *  应用用 history.replaceState 写回地址，不触发导航，所以在页面里轮询 location.href。 */
export async function queryParamIs(page: Page, name: string, value: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  try {
    await page.waitForFunction(queryParamEquals, { name, value }, { timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    const actual = await safeQueryParam(page, name);
    const actualDesc = actual === null ? "实际没有这个参数" : `实际 ${JSON.stringify(actual)}`;
    throw new DeterministicAssertion(`地址栏的 ${name} 参数应为 ${JSON.stringify(value)}，${actualDesc}（页面 ${page.url()}）`);
  }
}

// --- 动作：刷新页面 ---
/** 重新加载当前页面（地址不变），等到 load 事件；加载不完成算应用没达到期望（DeterministicAssertion）。 */
export async function reloadPage(page: Page, timeoutMs = RELOAD_TIMEOUT_MS): Promise<void> {
  const url = page.url();
  try {
    await page.reload({ waitUntil: "load", timeout: timeoutMs });
  } catch (e) {
    if (!isTimeout(e)) throw e;
    throw new DeterministicAssertion(`刷新页面在 ${timeoutMs / 1000} 秒内没有加载完成（页面 ${url}）`);
  }
}
