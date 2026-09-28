// steps/_home_and_language.mts 的本地单测（Midscene 侧判定逻辑）。
//
// 用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 .test. 文件。
// 与 test_home_and_language.py 同一套夹具：合成页（与应用同一套语言逻辑，是否写回地址、延迟生效、按钮隐藏、标题文案可配）
// 经 page.route 挂在一个 http 地址上走通过与失败两条路——地址栏参数与刷新都需要页面有真实地址；
// 真应用（file:// 打开 app/index.html，英文界面加 ?lang=en）验证选择器、真实文案、地址写回与刷新后保持，
// 答题中途切换复用 _checks 里的进度与得分判定。
//
// 运行：npm install && npx playwright install chromium && npm run test:steps
import { after, before, beforeEach, afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium, type Browser, type Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";
import * as checks from "./_checks.mts";
import * as hl from "./_home_and_language.mts";

const APP_INDEX = new URL("../app/index.html", import.meta.url);
const ORIGIN = "http://app.test";   // 合成页挂的假地址：page.route 拦下、不走网络

const ZH_TITLE = "识字大挑战 - 二年级上册", EN_TITLE = "Character Challenge - Grade 2, Volume 1";
const ZH_LABEL = "EN", EN_LABEL = "中文";   // 按钮上是切换目标语言的名字：中文界面显示 EN，英文界面显示 中文

interface Cfg {
  titleZh?: string; titleEn?: string; labelZh?: string; labelEn?: string;
  writeUrl?: boolean; applyDelayMs?: number; toggleHidden?: boolean;
}

/** 与应用同一套语言逻辑的最小页面：启动读 ?lang，切换时（可选）replaceState 写回地址、（可延迟）改标题与按钮文字。 */
function langHtml(cfg: Cfg = {}): string {
  const c = { titleZh: ZH_TITLE, titleEn: EN_TITLE, labelZh: ZH_LABEL, labelEn: EN_LABEL, writeUrl: true, applyDelayMs: 0, toggleHidden: false, ...cfg };
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${c.titleZh}</title>
<style>.hidden{display:none}</style></head><body>
<button id="lang-toggle" class="${c.toggleHidden ? "hidden" : ""}">
  ${c.labelZh}
</button>
<section id="home-screen"><h1 data-i18n="homeTitle">识字大挑战</h1><button id="start-btn">开始挑战</button></section>
<script>
  const CFG = ${JSON.stringify(c)};
  const I18N = { zh: { title: CFG.titleZh, toggle: CFG.labelZh }, en: { title: CFG.titleEn, toggle: CFG.labelEn } };
  let LANG = new URLSearchParams(location.search).get('lang') === 'en' ? 'en' : 'zh';
  function apply() {
    document.title = I18N[LANG].title;
    document.getElementById('lang-toggle').textContent = I18N[LANG].toggle;
  }
  function setLanguage(lang) {
    LANG = lang;
    if (CFG.writeUrl) { const u = new URL(location.href); u.searchParams.set('lang', LANG); history.replaceState(null, '', u); }
    if (CFG.applyDelayMs > 0) setTimeout(apply, CFG.applyDelayMs); else apply();
  }
  document.getElementById('lang-toggle').onclick = () => setLanguage(LANG === 'zh' ? 'en' : 'zh');
  apply();
</script></body></html>`;
}

let browser: Browser;
let page: Page;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });
beforeEach(async () => { page = await browser.newPage(); });
afterEach(async () => { await page.close(); });

/** 把合成页挂到 ORIGIN 下并打开（query 形如 "?lang=en"）；刷新时同一份 html 再次被送出。 */
async function serve(html: string, query = ""): Promise<void> {
  await page.route(`${ORIGIN}/**`, (route) => route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: html }));
  await page.goto(`${ORIGIN}/index.html${query}`);
}

/** 断言 p 以 DeterministicAssertion 拒绝（step 记 failed），且消息匹配 re。 */
async function rejectsAssertion(p: Promise<unknown>, re: RegExp): Promise<void> {
  await assert.rejects(p, (e: unknown) => {
    assert.ok(e instanceof DeterministicAssertion, `应抛 DeterministicAssertion，实际 ${(e as Error)?.constructor?.name}: ${(e as Error)?.message}`);
    assert.match((e as Error).message, re);
    return true;
  });
}

// --- 页面标题 ---
test("标题通过", async () => {
  await serve(langHtml());
  await hl.pageTitleIs(page, ZH_TITLE);
});

test("地址参数英文启动时标题是英文", async () => {
  await serve(langHtml(), "?lang=en");
  await hl.pageTitleIs(page, EN_TITLE);
});

test("标题判定会等晚到的变化", async () => {
  await serve(langHtml({ applyDelayMs: 300 }));
  await page.click("#lang-toggle");
  await hl.pageTitleIs(page, EN_TITLE, 3000);
});

test("标题不符时失败并带期望、实际与地址", async () => {
  await serve(langHtml({ titleZh: "识字挑战" }));
  await rejectsAssertion(hl.pageTitleIs(page, ZH_TITLE, 300), /页面标题应为 "识字大挑战 - 二年级上册"，实际 "识字挑战"（页面 http:\/\/app\.test\/index\.html）/);
});

test("标题是整段匹配不是子串", async () => {
  await serve(langHtml());
  await rejectsAssertion(hl.pageTitleIs(page, "识字大挑战", 300), /页面标题应为 "识字大挑战"，实际 "识字大挑战 - 二年级上册"/);
});

test("标题期望里的空白会归一", async () => {
  await serve(langHtml());
  await hl.pageTitleIs(page, "  识字大挑战  -   二年级上册 ");
});

// --- 语言切换按钮 ---
test("切换按钮通过（按钮文字外的换行缩进折叠后恰为 EN）", async () => {
  await serve(langHtml());
  await hl.langToggleShows(page, ZH_LABEL);
});

test("英文界面下切换按钮显示 中文", async () => {
  await serve(langHtml(), "?lang=en");
  await hl.langToggleShows(page, EN_LABEL);
});

test("切换按钮判定会等晚到的变化", async () => {
  await serve(langHtml({ applyDelayMs: 300 }));
  await page.click("#lang-toggle");
  await hl.langToggleShows(page, EN_LABEL, 3000);
});

test("切换按钮文字不符时失败并带期望、实际与选择器", async () => {
  await serve(langHtml());
  await rejectsAssertion(hl.langToggleShows(page, EN_LABEL, 300), /语言切换按钮应显示 "中文"，实际 "EN"（页面 http:\/\/app\.test\/index\.html，选择器 #lang-toggle）/);
});

test("切换按钮文字是整段匹配不是子串", async () => {
  await serve(langHtml());
  await rejectsAssertion(hl.langToggleShows(page, "E", 300), /语言切换按钮应显示 "E"，实际 "EN"/);
});

test("切换按钮隐藏时按没有显示失败", async () => {
  await serve(langHtml({ toggleHidden: true }));
  await rejectsAssertion(hl.langToggleShows(page, ZH_LABEL, 300), /语言切换按钮没有显示（页面 http:\/\/app\.test\/index\.html，选择器 #lang-toggle）/);
});

test("切换按钮不存在时按没有显示失败", async () => {
  await page.setContent("<button id='start-btn'>开始挑战</button>");
  await rejectsAssertion(hl.langToggleShows(page, ZH_LABEL, 300), /语言切换按钮没有显示.*#lang-toggle/);
});

// --- 地址栏参数 ---
test("地址栏参数：启动地址里就有", async () => {
  await serve(langHtml(), "?lang=en");
  await hl.queryParamIs(page, "lang", "en");
});

test("地址栏参数：replaceState 写回后能读到，切回也能读到", async () => {
  await serve(langHtml());
  await page.click("#lang-toggle");
  await hl.queryParamIs(page, "lang", "en");
  await page.click("#lang-toggle");
  await hl.queryParamIs(page, "lang", "zh");
});

test("地址栏参数判定会等晚到的 replaceState", async () => {
  await serve(langHtml());
  await page.evaluate(() => setTimeout(() => history.replaceState(null, "", "?lang=en"), 300));
  await hl.queryParamIs(page, "lang", "en", 3000);
});

test("地址栏没有这个参数时失败并说明", async () => {
  await serve(langHtml());
  await rejectsAssertion(hl.queryParamIs(page, "lang", "zh", 300), /地址栏的 lang 参数应为 "zh"，实际没有这个参数（页面 http:\/\/app\.test\/index\.html）/);
});

test("地址栏参数取值不符时失败并带实际值", async () => {
  await serve(langHtml({ writeUrl: false }), "?lang=zh");
  await page.click("#lang-toggle");   // 界面切了，但地址没写回
  await hl.langToggleShows(page, EN_LABEL);
  await rejectsAssertion(hl.queryParamIs(page, "lang", "en", 300), /地址栏的 lang 参数应为 "en"，实际 "zh"（页面 http:\/\/app\.test\/index\.html\?lang=zh）/);
});

test("地址栏参数是逐字相等不是前缀", async () => {
  await serve(langHtml(), "?lang=english");
  await rejectsAssertion(hl.queryParamIs(page, "lang", "en", 300), /地址栏的 lang 参数应为 "en"，实际 "english"/);
});

// --- 刷新页面 ---
test("刷新后地址不变、语言按地址重新生效", async () => {
  await serve(langHtml());
  await page.click("#lang-toggle");
  await hl.queryParamIs(page, "lang", "en");
  await hl.reloadPage(page);
  assert.equal(page.url(), `${ORIGIN}/index.html?lang=en`);
  await hl.pageTitleIs(page, EN_TITLE);
  await hl.langToggleShows(page, EN_LABEL);
});

test("刷新超时按没有加载完成失败并带地址", async () => {
  await serve(langHtml());
  // 刷新时让请求一直挂着：超时算应用没达到期望
  await page.unroute(`${ORIGIN}/**`);
  await page.route(`${ORIGIN}/**`, () => { /* 不响应 */ });
  await rejectsAssertion(hl.reloadPage(page, 500), /刷新页面在 0\.5 秒内没有加载完成（页面 http:\/\/app\.test\/index\.html）/);
});

// --- 真应用：选择器、真实文案、地址写回、刷新后保持、答题中途切换 ---
const openApp = (lang?: string) => page.goto(APP_INDEX.href + (lang ? `?lang=${lang}` : ""));

test("真应用：中文主页", async () => {
  await openApp();
  await hl.pageTitleIs(page, ZH_TITLE);
  await hl.langToggleShows(page, ZH_LABEL);
  // 缺省中文时地址栏没有参数（需求：不带参数为中文）
  await rejectsAssertion(hl.queryParamIs(page, "lang", "zh", 300), /地址栏的 lang 参数应为 "zh"，实际没有这个参数/);
});

test("真应用：地址参数英文启动", async () => {
  await openApp("en");
  await hl.pageTitleIs(page, EN_TITLE);
  await hl.langToggleShows(page, EN_LABEL);
  await hl.queryParamIs(page, "lang", "en");
});

test("真应用：切换再切回", async () => {
  await openApp();
  await page.click("#lang-toggle");
  await hl.pageTitleIs(page, EN_TITLE);
  await hl.langToggleShows(page, EN_LABEL);
  await hl.queryParamIs(page, "lang", "en");
  await page.click("#lang-toggle");
  await hl.pageTitleIs(page, ZH_TITLE);
  await hl.langToggleShows(page, ZH_LABEL);
  await hl.queryParamIs(page, "lang", "zh");
});

test("真应用：切到英文后刷新仍是英文", async () => {
  await openApp();
  await page.click("#lang-toggle");
  await hl.queryParamIs(page, "lang", "en");
  await hl.reloadPage(page);
  await hl.pageTitleIs(page, EN_TITLE);
  await hl.langToggleShows(page, EN_LABEL);
  await hl.queryParamIs(page, "lang", "en");
});

test("真应用：答题中途切换语言不丢状态", async () => {
  await openApp();
  await page.click("#start-btn");
  await page.locator("#level-grid button").first().click();
  await checks.answerCorrect(page);
  await checks.scoreIs(page, "1");
  await checks.progressIs(page, "2", "10");   // 等 1.5 秒自动切到第 2 题
  const word = await page.locator("#current-word").textContent();
  const options = await page.locator("#options-container .option-btn").allTextContents();
  await page.click("#lang-toggle");
  await hl.langToggleShows(page, EN_LABEL);
  await hl.queryParamIs(page, "lang", "en");
  await hl.pageTitleIs(page, EN_TITLE);
  await checks.progressIs(page, "2", "10");
  await checks.scoreIs(page, "1");
  assert.equal(await page.locator("#current-word").textContent(), word);
  assert.deepEqual(await page.locator("#options-container .option-btn").allTextContents(), options);
});

test("合成页的选择器与文案在应用源码里真实存在", () => {
  const src = readFileSync(fileURLToPath(APP_INDEX), "utf-8");
  assert.ok(src.includes(`id="${hl.SEL_LANG_TOGGLE.slice(1)}"`), `app/index.html 里找不到 ${hl.SEL_LANG_TOGGLE}`);
  assert.ok(src.includes(`<title>${ZH_TITLE}</title>`));
  for (const text of [ZH_TITLE, EN_TITLE, ZH_LABEL, EN_LABEL]) assert.ok(src.includes(text), `app/index.html 里找不到文案 ${text}`);
});
