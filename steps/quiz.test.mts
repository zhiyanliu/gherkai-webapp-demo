// steps/_checks.mts 的本地单测（Midscene 侧判定逻辑）。
//
// 用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 .test. 文件。
// 与 test_checks.py 同一套夹具：合成页（可配切题时长等）走通过与失败两条路；真应用（file:// 打开 app/index.html）
// 验证选择器、题库副本与真实的 1.5 秒 / 3 秒切题时长。
//
// 运行：npm install && npx playwright install chromium && npm run test:steps
import { after, before, beforeEach, afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium, type Browser, type Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";
import * as checks from "./_checks.mts";

const APP_INDEX = new URL("../app/index.html", import.meta.url);

interface Cfg {
  score?: number; current?: number; total?: number;
  correctDelay?: number; wrongDelay?: number; advance?: boolean; nextQuestion?: string; incrementScore?: boolean;
}

/** 与应用同结构的最小答题页：同样的 id / class、同样的一题只答一次与切题逻辑，时长可配。 */
function quizHtml(word: string, options: string[], correct: string, cfg: Cfg = {}): string {
  const c = { score: 0, current: 1, total: 10, correctDelay: 300, wrongDelay: 600, advance: true, nextQuestion: "2", incrementScore: true, ...cfg };
  return `<!doctype html><html><body>
<section id="game-screen">
<div><span id="score-display">${c.score}</span></div>
<div><span id="current-q">${c.current}</span> / <span id="total-q">${c.total}</span></div>
<div><span id="current-word">${word}</span></div>
<div id="options-container"></div>
</section>
<script>
  const CORRECT = ${JSON.stringify(correct)};
  const OPTIONS = ${JSON.stringify(options)};
  const CFG = ${JSON.stringify(c)};
  let answering = false;
  const box = document.getElementById('options-container');
  function render() {
    box.innerHTML = '';
    OPTIONS.forEach(opt => {
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.textContent = opt;
      b.onclick = () => handle(b, opt);
      box.appendChild(b);
    });
  }
  function handle(btn, selected) {
    if (answering) return;
    answering = true;
    const ok = selected === CORRECT;
    if (ok) {
      btn.classList.add('correct');
      if (CFG.incrementScore) {
        const s = document.getElementById('score-display');
        s.textContent = String(Number(s.textContent) + 1);
      }
    } else {
      btn.classList.add('wrong');
      document.querySelectorAll('.option-btn').forEach(b => { if (b.textContent === CORRECT) b.classList.add('correct'); });
    }
    if (CFG.advance) {
      setTimeout(() => {
        document.getElementById('current-q').textContent = CFG.nextQuestion;
        answering = false;
        render();
      }, ok ? CFG.correctDelay : CFG.wrongDelay);
    }
  }
  render();
</script></body></html>`;
}

const WORD = "两", CORRECT = "liǎng";
const OPTIONS = ["nǎ", "liǎng", "pí", "dù"];

let browser: Browser;
let page: Page;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });
beforeEach(async () => { page = await browser.newPage(); });
afterEach(async () => { await page.close(); });

const load = (cfg: Cfg = {}) => page.setContent(quizHtml(WORD, OPTIONS, CORRECT, cfg));

/** 断言 p 以 DeterministicAssertion 拒绝（step 记 failed），且消息匹配 re。 */
async function rejectsAssertion(p: Promise<unknown>, re: RegExp): Promise<void> {
  await assert.rejects(p, (e: unknown) => {
    assert.ok(e instanceof DeterministicAssertion, `应抛 DeterministicAssertion，实际 ${(e as Error)?.constructor?.name}: ${(e as Error)?.message}`);
    assert.match((e as Error).message, re);
    return true;
  });
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// --- 题库：规格在需求文档附录 A，steps/_vocabulary.json 是它的副本；应用源码必须与规格一致 ---
const REQUIREMENTS = new URL("../docs/product-requirements.md", import.meta.url);

function vocabularyFromRequirements(): Map<string, string> {
  const text = readFileSync(fileURLToPath(REQUIREMENTS), "utf-8");
  const appendix = text.split("## 附录 A：题库", 2)[1];
  const spec = new Map<string, string>();
  for (const m of appendix.matchAll(/^\| (\S) \| (\S+) \|$/gm)) spec.set(m[1], m[2]);
  return spec;
}

test("题库副本与需求文档附录 A 一致", () => {
  const spec = vocabularyFromRequirements();
  assert.equal(spec.size, 81);
  assert.deepEqual(Object.fromEntries(checks.loadVocabulary()), Object.fromEntries(spec));
});

test("应用源码的题库与规格一致（判的是应用，不是规格）", () => {
  const src = readFileSync(fileURLToPath(APP_INDEX), "utf-8");
  const block = /const VOCABULARY = \[(.*?)\];/s.exec(src)![1];
  const fromApp = new Map<string, string>();
  for (const m of block.matchAll(/\{\s*word:\s*'([^']+)',\s*pinyin:\s*'([^']+)'\s*\}/g)) fromApp.set(m[1], m[2]);
  assert.equal(fromApp.size, 81);
  assert.deepEqual(Object.fromEntries(fromApp), Object.fromEntries(checks.loadVocabulary()), "应用题库与规格不一致");
});

// --- 进度、得分、选项个数 ---
test("进度与得分通过", async () => {
  await load();
  await checks.progressIs(page, "1", "10");
  await checks.scoreIs(page, "0");
});

test("进度不符时失败并带现场", async () => {
  await load({ current: 2 });
  await rejectsAssertion(checks.progressIs(page, "1", "10", 300), /进度的当前题号应为 "1"，实际 "2".*#current-q/);
});

test("得分是整段匹配不是子串", async () => {
  await load({ score: 10 });
  await rejectsAssertion(checks.scoreIs(page, "1", 300), /得分应为 "1"，实际 "10".*#score-display/);
});

test("得分判定会等晚到的更新", async () => {
  await load();
  await page.evaluate(() => setTimeout(() => { document.getElementById("score-display")!.textContent = "1"; }, 200));
  await checks.scoreIs(page, "1", 2000);
});

test("选项个数通过", async () => {
  await load();
  await checks.optionCountIs(page, 4);
});

test("选项个数不符时列出选项", async () => {
  await page.setContent(quizHtml(WORD, ["nǎ", "liǎng", "pí"], CORRECT));
  await rejectsAssertion(checks.optionCountIs(page, 4, 300), /拼音选项应有 4 个，实际 3 个：\["nǎ","liǎng","pí"\].*#options-container \.option-btn/);
});

test("有选项没有文字时失败", async () => {
  await page.setContent(quizHtml(WORD, ["nǎ", "liǎng", "", "dù"], CORRECT));
  await rejectsAssertion(checks.optionCountIs(page, 4, 300), /第 \[3\] 个拼音选项没有文字/);
});

// --- 按题库作答 ---
test("选正确拼音：按题库点对应选项", async () => {
  await load();
  assert.equal(await checks.answerCorrect(page), CORRECT);
  assert.equal(await page.locator("#options-container .option-btn.correct").textContent(), CORRECT);
  await checks.scoreIs(page, "1");
});

test("选正确拼音：等选项渲染出来再点", async () => {
  await page.setContent('<span id="current-q">1</span><span id="current-word"></span><div id="options-container"></div>');
  await page.evaluate(() => setTimeout(() => {
    document.getElementById("current-word")!.textContent = "两";
    const box = document.getElementById("options-container")!;
    for (const t of ["pí", "liǎng"]) { const b = document.createElement("button"); b.className = "option-btn"; b.textContent = t; box.appendChild(b); }
  }, 300));
  assert.equal(await checks.answerCorrect(page, 3000), CORRECT);
});

test("选正确拼音：生字不在题库副本里时失败", async () => {
  await page.setContent(quizHtml("龘", OPTIONS, CORRECT));
  await rejectsAssertion(checks.answerCorrect(page), /「龘」不在题库副本 _vocabulary\.json 里/);
});

test("选正确拼音：正确拼音不在选项里时失败", async () => {
  await page.setContent(quizHtml(WORD, ["nǎ", "pí", "dù", "tā"], CORRECT));
  await rejectsAssertion(checks.answerCorrect(page), /「两」的正确拼音 "liǎng" 不在选项里：当前选项 \["nǎ","pí","dù","tā"\]/);
});

test("选正确拼音：正确拼音出现多次时失败", async () => {
  await page.setContent(quizHtml(WORD, ["liǎng", "pí", "liǎng", "dù"], CORRECT));
  await rejectsAssertion(checks.answerCorrect(page), /在选项里出现了 2 次/);
});

test("选正确拼音：答题页没就位时失败", async () => {
  await page.setContent('<div id="options-container"></div><span id="current-word"></span>');
  await rejectsAssertion(checks.answerCorrect(page, 300), /答题页没有就位/);
});

test("选错误拼音：点第一个不是正确答案的选项", async () => {
  await load();
  assert.equal(await checks.answerWrong(page), "nǎ");
  assert.equal(await page.locator("#options-container .option-btn.wrong").textContent(), "nǎ");
  assert.equal(await page.locator("#options-container .option-btn.correct").textContent(), CORRECT);
  await checks.scoreIs(page, "0");
});

test("选错误拼音：没有错误选项时失败", async () => {
  await page.setContent(quizHtml(WORD, ["liǎng"], CORRECT));
  await rejectsAssertion(checks.answerWrong(page), /没有「两」（"liǎng"）以外的错误拼音/);
});

// --- 一题只答一次 ---
test("作答后再点另一个选项：得分与高亮不变", async () => {
  await load();
  await checks.answerCorrect(page);
  const other = await checks.clickAnotherUnhighlightedOption(page);
  assert.ok(OPTIONS.includes(other) && other !== CORRECT);
  await checks.scoreIs(page, "1");
  await checks.highlightCountsAre(page, 1, 0);
});

test("没作答就再点：失败并报当前题号", async () => {
  await load();
  await rejectsAssertion(checks.clickAnotherUnhighlightedOption(page), /没有已作答的高亮选项（当前第 1 题）/);
});

test("高亮个数不符时报实际值", async () => {
  await load();
  await checks.answerWrong(page);
  await rejectsAssertion(checks.highlightCountsAre(page, 1, 0), /应有 1 个、答错状态的应有 0 个，实际答对 1 个、答错 1 个（第 1 题/);
});

// --- 自动切题时长 ---
test("自动切题：量出时长并核对新题号", async () => {
  await load({ correctDelay: 600 });
  await checks.answerCorrect(page);
  const measured = await checks.autoAdvance(page, 0.6, "2");
  assert.ok(measured >= 0.55 && measured <= 0.9, `measured ${measured}`);
});

test("自动切题：中间隔着耗时步骤仍量得准", async () => {
  await load({ correctDelay: 600 });
  await checks.answerCorrect(page);
  await sleep(1500); // 模拟中间隔着一条耗时的 AI 步：切题早已发生，时长仍由页面里的探针给出
  const measured = await checks.autoAdvance(page, 0.6, "2");
  assert.ok(measured >= 0.55 && measured <= 0.9, `measured ${measured}`);
});

test("自动切题：时长不符时失败", async () => {
  await load({ wrongDelay: 600 });
  await checks.answerWrong(page);
  await rejectsAssertion(checks.autoAdvance(page, 1.5, "2"), /作答后自动进入下一题用了 0\.6\d 秒，期望 1\.5 秒（容差 ±0\.4 秒）/);
});

test("自动切题：一直不切题时失败", async () => {
  await load({ advance: false });
  await checks.answerCorrect(page);
  await rejectsAssertion(checks.autoAdvance(page, 0.5, "2"), /作答后 0\.5 秒（容差 ±0\.4 秒）内没有自动进入下一题，仍在第 1 题/);
});

test("自动切题：切到别的题号时失败", async () => {
  await load({ correctDelay: 300, nextQuestion: "3" });
  await checks.answerCorrect(page);
  await rejectsAssertion(checks.autoAdvance(page, 0.3, "2"), /自动进入的是第 3 题，期望第 2 题/);
});

test("自动切题：前面没有作答步是用例写法错误（普通 Error，不是断言）", async () => {
  await load();
  await assert.rejects(checks.autoAdvance(page, 1.5, "2"), (e: unknown) => {
    assert.ok(e instanceof Error && !(e instanceof DeterministicAssertion));
    assert.match((e as Error).message, /没有作答记录/);
    return true;
  });
});

test("连续作答两次：第二次用新的探针", async () => {
  await load({ correctDelay: 300 });
  await checks.answerCorrect(page);
  await checks.autoAdvance(page, 0.3, "2");
  await page.evaluate(() => { document.getElementById("current-word")!.textContent = "两"; });
  await checks.answerCorrect(page);
  // 合成页每次都切到 "2"：第二次作答后题号不变，探针（新起点 "2"）就不会记到切题 → 说明用的是新探针
  await rejectsAssertion(checks.autoAdvance(page, 0.3, "3"), /内没有自动进入下一题/);
});

// --- 真应用：选择器、题库副本与真实切题时长 ---
async function enterGroup1(): Promise<void> {
  await page.goto(APP_INDEX.href);
  await page.click("#start-btn");
  await page.locator("#level-grid button").first().click();
}

test("真应用：进入第 1 组后的初始状态", async () => {
  await enterGroup1();
  await checks.optionCountIs(page, 4);
  await checks.progressIs(page, "1", "10");
  await checks.scoreIs(page, "0");
});

test("真应用：答对加一分、1.5 秒后进入第 2 题", async () => {
  await enterGroup1();
  await checks.answerCorrect(page);
  await checks.scoreIs(page, "1");
  await checks.highlightCountsAre(page, 1, 0);
  await checks.autoAdvance(page, 1.5, "2");
  await checks.progressIs(page, "2", "10");
});

test("真应用：答错不加分、高亮正确答案、3 秒后进入第 2 题", async () => {
  await enterGroup1();
  await checks.answerWrong(page);
  await checks.scoreIs(page, "0");
  await checks.highlightCountsAre(page, 1, 1);
  await checks.autoAdvance(page, 3, "2");
});

test("真应用：一题只答一次", async () => {
  await enterGroup1();
  await checks.answerCorrect(page);
  await checks.clickAnotherUnhighlightedOption(page);
  await checks.scoreIs(page, "1");
  await checks.highlightCountsAre(page, 1, 0);
});

test("真应用：主页上判进度与得分要失败（答题页未显示）", async () => {
  await page.goto(APP_INDEX.href);
  await page.waitForSelector("#start-btn");
  await assert.rejects(checks.progressIs(page, "1", "10", 800), (e: unknown) => e instanceof DeterministicAssertion && /答题页未显示/.test((e as Error).message));
  await assert.rejects(checks.scoreIs(page, "0", 800), (e: unknown) => e instanceof DeterministicAssertion && /答题页未显示/.test((e as Error).message));
});
