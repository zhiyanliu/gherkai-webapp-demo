// steps/_level_select.mts 的本地单测（Midscene 侧判定逻辑）。
//
// 用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 .test. 文件。
// 与 test_level_select.py 同一套夹具：合成页（四页骨架、关卡按钮可配）走通过与失败两条路；真应用（file:// 打开
// app/index.html，英文界面加 ?lang=en）验证选择器与真实文案；进入第 3 组后复用 _checks 里的进度与得分判定。
//
// 运行：npm install && npx playwright install chromium && npm run test:steps
import { after, before, beforeEach, afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium, type Browser, type Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";
import * as checks from "./_checks.mts";
import * as ls from "./_level_select.mts";

const APP_INDEX = new URL("../app/index.html", import.meta.url);

const zhName = (n: number) => `第 ${n} 组`;
const enName = (n: number) => `Group ${n}`;

interface Cfg {
  screen?: "home" | "level" | "game" | "result";
  title?: string;
  count?: number;
  name?: (n: number) => string;
  sub?: string;
  overrides?: Record<number, string>;
  back?: string;
  start?: string;
}

/** 与应用同结构的最小页面：四个页面节点都在 DOM 里、靠 hidden 切换；关卡按钮两行（关卡名、副标题）。
 *  overrides 按 1 起的序号替换某个按钮的整段 innerHTML，用来造出文案错误。 */
function levelHtml(cfg: Cfg = {}): string {
  const c = { screen: "level", title: "选择关卡", count: 8, name: zhName, sub: "10 个生字", overrides: {}, back: "返回主页", start: "开始挑战", ...cfg };
  const buttons: string[] = [];
  for (let i = 1; i <= c.count; i++) {
    const inner = (c.overrides as Record<number, string>)[i] ?? `<div>${c.name(i)}</div><div>${c.sub}</div>`;
    buttons.push(`<button>${inner}</button>`);
  }
  const hidden = (s: string) => (s === c.screen ? "" : "hidden");
  return `<!doctype html><html><head><style>.hidden{display:none}</style></head><body>
<button id="lang-toggle">EN</button>
<section id="home-screen" class="${hidden("home")}">
  <h1>识字大挑战</h1>
  <button id="start-btn"><img alt="开始按钮"><span>
      ${c.start}
  </span></button>
</section>
<section id="level-screen" class="${hidden("level")}">
  <h2>${c.title}</h2>
  <div id="level-grid">${buttons.join("")}</div>
  <button id="back-home-btn">${c.back}</button>
</section>
<section id="game-screen" class="${hidden("game")}">
  <span id="score-display">0</span><span id="current-q">1</span> / <span id="total-q">10</span>
</section>
<section id="result-screen" class="${hidden("result")}">
  <button id="replay-btn">再玩一次</button><button id="home-btn">返回主页</button>
</section>
</body></html>`;
}

let browser: Browser;
let page: Page;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });
beforeEach(async () => { page = await browser.newPage(); });
afterEach(async () => { await page.close(); });

const load = (cfg: Cfg = {}) => page.setContent(levelHtml(cfg));

/** 模拟点了开始挑战之后页面切换：ms 后隐藏主页、显示选关页。 */
const showLevelAfter = (ms: number) => page.evaluate((ms) => setTimeout(() => {
  document.getElementById("home-screen")!.classList.add("hidden");
  document.getElementById("level-screen")!.classList.remove("hidden");
}, ms), ms);

/** 断言 p 以 DeterministicAssertion 拒绝（step 记 failed），且消息匹配 re。 */
async function rejectsAssertion(p: Promise<unknown>, re: RegExp): Promise<void> {
  await assert.rejects(p, (e: unknown) => {
    assert.ok(e instanceof DeterministicAssertion, `应抛 DeterministicAssertion，实际 ${(e as Error)?.constructor?.name}: ${(e as Error)?.message}`);
    assert.match((e as Error).message, re);
    return true;
  });
}

// --- 标题 ---
test("标题通过", async () => {
  await load();
  await ls.levelTitleIs(page, "选择关卡");
});

test("标题判定会等选关页出现", async () => {
  await load({ screen: "home" });
  await showLevelAfter(300);
  await ls.levelTitleIs(page, "选择关卡", 3000);
});

test("选关页没显示时失败并说出当前是哪一页", async () => {
  await load({ screen: "home" });
  await rejectsAssertion(ls.levelTitleIs(page, "选择关卡", 300), /选关页没有显示：当前显示的是 主页.*#level-screen/);
});

test("标题不符时失败并带期望与实际", async () => {
  await load({ title: "选关" });
  await rejectsAssertion(ls.levelTitleIs(page, "选择关卡", 300), /选关页标题应为 "选择关卡"，实际 "选关".*#level-screen h2/);
});

test("标题是整段匹配不是子串", async () => {
  await load({ title: "请选择关卡" });
  await rejectsAssertion(ls.levelTitleIs(page, "选择关卡", 300), /选关页标题应为 "选择关卡"，实际 "请选择关卡"/);
});

// --- 按钮个数 ---
test("按钮个数通过", async () => {
  await load();
  await ls.levelButtonCountIs(page, 8);
});

test("按钮个数不符时列出按钮", async () => {
  await load({ count: 7 });
  await rejectsAssertion(
    ls.levelButtonCountIs(page, 8, 300),
    /关卡按钮应有 8 个，实际 7 个：\["第 1 组 10 个生字",.*"第 7 组 10 个生字"\].*#level-grid button/,
  );
});

test("选关页没显示时按钮个数判定失败（DOM 里一直有 8 个按钮）", async () => {
  await load({ screen: "home" });
  await rejectsAssertion(ls.levelButtonCountIs(page, 8, 300), /选关页没有显示：当前显示的是 主页/);
});

// --- 按钮文案 ---
test("中文文案通过", async () => {
  await load();
  assert.deepEqual(await ls.levelButtonsLabeled(page, "第 N 组", "10 个生字"), [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `第 ${i} 组 10 个生字`));
});

test("英文文案通过", async () => {
  await load({ title: "Choose a Level", name: enName, sub: "10 characters" });
  await ls.levelButtonsLabeled(page, "Group N", "10 characters");
});

test("组号错时失败并点名那个按钮", async () => {
  await load({ overrides: { 3: "<div>第 4 组</div><div>10 个生字</div>" } });
  await rejectsAssertion(
    ls.levelButtonsLabeled(page, "第 N 组", "10 个生字"),
    /关卡按钮的文案不符（共 8 个按钮，1 个不符）：第 3 个应标注「第 3 组」与「10 个生字」，实际 "第 4 组 10 个生字"（页面/,
  );
});

test("副标题错时列出每个不符的按钮", async () => {
  await load({ overrides: { 5: "<div>第 5 组</div><div>9 个生字</div>", 8: "<div>第 8 组</div>" } });
  await rejectsAssertion(
    ls.levelButtonsLabeled(page, "第 N 组", "10 个生字"),
    /（共 8 个按钮，2 个不符）：第 5 个应标注.*实际 "第 5 组 9 个生字"；第 8 个应标注.*实际 "第 8 组"/,
  );
});

test("两行黏在一起时判不符", async () => {
  await load({ overrides: { 2: "<div>第 2 组10 个生字</div>" } });
  await rejectsAssertion(ls.levelButtonsLabeled(page, "第 N 组", "10 个生字"), /第 2 个应标注「第 2 组」与「10 个生字」，实际 "第 2 组10 个生字"/);
});

test("模板里没有 N 是用例写法错误（普通 Error，不是断言）", async () => {
  await load();
  await assert.rejects(ls.levelButtonsLabeled(page, "第 1 组", "10 个生字"), (e: unknown) => {
    assert.ok(e instanceof Error && !(e instanceof DeterministicAssertion));
    assert.match((e as Error).message, /关卡名模板 "第 1 组" 里没有字母 N/);
    return true;
  });
});

test("没有关卡按钮时失败", async () => {
  await load({ count: 0 });
  await rejectsAssertion(ls.levelButtonsLabeled(page, "第 N 组", "10 个生字", 300), /选关页上没有关卡按钮.*#level-grid button/);
});

test("选关页没显示时文案判定失败", async () => {
  await load({ screen: "home" });
  await rejectsAssertion(ls.levelButtonsLabeled(page, "第 N 组", "10 个生字", 300), /选关页没有显示：当前显示的是 主页/);
});

test("期望文案：模板里每个 N 都代入", () => {
  assert.equal(ls.expectedLevelLabel("第 N 组", "10 个生字", 3), "第 3 组 10 个生字");
  assert.equal(ls.expectedLevelLabel("Group N", "10 characters", 8), "Group 8 10 characters");
  assert.equal(ls.expectedLevelLabel("N-N", "x", 2), "2-2 x");
});

// --- 页面上有某个按钮 ---
test("选关页上有返回主页按钮", async () => {
  await load();
  await ls.hasVisibleButton(page, "返回主页");
});

test("按可见文字判、不按 accessible name（开始按钮里有 alt 图片与换行缩进）", async () => {
  await load({ screen: "home" });
  await ls.hasVisibleButton(page, "开始挑战");
});

test("按钮文字是整段匹配不是子串", async () => {
  await load();
  await rejectsAssertion(
    ls.hasVisibleButton(page, "返回", 300),
    /页面上没有文字为 "返回" 的可见按钮，当前可见的按钮：\["EN","第 1 组 10 个生字",.*"返回主页"\]（当前显示的是 选关页；页面 .*选择器 button）/,
  );
});

test("隐藏的按钮不算（结算页里也有返回主页）", async () => {
  await load({ screen: "home" });
  await rejectsAssertion(
    ls.hasVisibleButton(page, "返回主页", 300),
    /页面上没有文字为 "返回主页" 的可见按钮，当前可见的按钮：\["EN","开始挑战"\]（当前显示的是 主页/,
  );
});

test("按钮判定会等晚出现的页面", async () => {
  await load({ screen: "home" });
  await showLevelAfter(300);
  await ls.hasVisibleButton(page, "返回主页", 3000);
});

test("期望文字里的空白也归一", async () => {
  await load();
  await ls.hasVisibleButton(page, "  返回主页 ");
});

// --- 真应用：选择器、真实文案、两种语言 ---
async function openLevelScreen(lang?: string): Promise<void> {
  await page.goto(APP_INDEX.href + (lang ? `?lang=${lang}` : ""));
  await page.click("#start-btn");
}

test("真应用：中文选关页", async () => {
  await openLevelScreen();
  await ls.levelTitleIs(page, "选择关卡");
  await ls.levelButtonCountIs(page, 8);
  await ls.levelButtonsLabeled(page, "第 N 组", "10 个生字");
  await ls.hasVisibleButton(page, "返回主页");
});

test("真应用：英文选关页", async () => {
  await openLevelScreen("en");
  await ls.levelTitleIs(page, "Choose a Level");
  await ls.levelButtonCountIs(page, 8);
  await ls.levelButtonsLabeled(page, "Group N", "10 characters");
  await ls.hasVisibleButton(page, "Back to Home");
});

test("真应用：主页上过不了选关页的判定", async () => {
  await page.goto(APP_INDEX.href);
  await ls.hasVisibleButton(page, "开始挑战");
  await rejectsAssertion(ls.levelButtonCountIs(page, 8, 300), /选关页没有显示：当前显示的是 主页/);
  await rejectsAssertion(ls.hasVisibleButton(page, "返回主页", 300), /页面上没有文字为 "返回主页" 的可见按钮/);
});

test("真应用：返回主页", async () => {
  await openLevelScreen();
  await ls.hasVisibleButton(page, "返回主页");
  await page.click("#back-home-btn");
  await ls.hasVisibleButton(page, "开始挑战");
  await rejectsAssertion(ls.levelTitleIs(page, "选择关卡", 300), /选关页没有显示：当前显示的是 主页/);
});

test("真应用：进入第 3 组后是第 1 题、得分 0", async () => {
  await openLevelScreen();
  await page.locator("#level-grid button").nth(2).click();
  await checks.progressIs(page, "1", "10");
  await checks.scoreIs(page, "0");
  await rejectsAssertion(ls.levelTitleIs(page, "选择关卡", 300), /选关页没有显示：当前显示的是 答题页/);
});

test("合成页用的 id 在应用源码里都真实存在", () => {
  const src = readFileSync(fileURLToPath(APP_INDEX), "utf-8");
  for (const id of ["home-screen", "level-screen", "level-grid", "back-home-btn", "start-btn", "game-screen", "result-screen", "home-btn"]) {
    assert.ok(src.includes(`id="${id}"`), `app/index.html 里找不到 id="${id}"`);
  }
  for (const [, sel] of ls.SCREENS) assert.ok(src.includes(`id="${sel.slice(1)}"`), `app/index.html 里找不到 ${sel}`);
});
