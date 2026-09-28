// steps/_result.mts 的本地单测（Midscene 侧判定逻辑）。
//
// 用本地 Chromium 跑，不开云端浏览器会话、不调模型、不需要 AWS 凭证。worker 加载 steps/ 时跳过 .test. 文件。
// 与 test_result.py 同一套夹具：合成页（与应用同结构的最小四页骨架加可配置的答题流程：题数、几百毫秒的切题时长、
// 答完第几题进结算页、跳题、不切题、初始显示哪一页、结算页上的得分与评语；题目取自题库副本里的生字）走通过与失败两条路；
// 真应用（file:// 打开 app/index.html，英文界面加 ?lang=en）验证选择器、真实文案与真实的 1.5 秒 / 3 秒切题节奏下
// 连答 10 题能到结算页；再玩一次与返回主页复用 _checks 与 _level_select 里的判定。
//
// 运行：npm install && npx playwright install chromium && npm run test:steps
import { after, before, beforeEach, afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { chromium, type Browser, type Page } from "playwright";
import { DeterministicAssertion } from "@gherkai/worker-midscene";
import * as checks from "./_checks.mts";
import { hasVisibleButton } from "./_level_select.mts";
import * as result from "./_result.mts";

const APP_INDEX = new URL("../app/index.html", import.meta.url);

// 合成页用的题目：都在题库副本里（_checks 按题库查拼音）；拼音互不相同，做干扰项不会撞上正确答案
const VOCAB: Array<[string, string]> = [
  ["两", "liǎng"], ["哪", "nǎ"], ["宽", "kuān"], ["顶", "dǐng"], ["肚", "dù"], ["皮", "pí"],
  ["孩", "hái"], ["跳", "tiào"], ["变", "biàn"], ["极", "jí"], ["片", "piàn"], ["傍", "bàng"],
];

const MSG_PERFECT = "太厉害了！全对！🌟";
const MSG_GOOD = "真棒！继续加油！✨";
const MSG_TRY_AGAIN = "再接再厉哦！💪";

interface Cfg {
  screen?: string; total?: number; startAt?: number; correctDelay?: number; wrongDelay?: number;
  advance?: boolean; endAfter?: number; jumpTo?: Record<string, number>;
  finalScore?: number | null; message?: string | null; title?: string;
}

/** 与应用同结构的最小四页骨架加可配置的答题流程（各项含义见 test_result.py 的 result_html）。 */
function resultHtml(cfg: Cfg = {}): string {
  const c = {
    screen: "game", total: 10, startAt: 1, correctDelay: 100, wrongDelay: 200, advance: true,
    jumpTo: {}, finalScore: null, message: null, title: "挑战完成！", ...cfg,
  };
  const endAfter = cfg.endAfter ?? c.total;
  const words = VOCAB.map(([word, pinyin]) => ({ word, pinyin }));
  return `<!doctype html><html><head><style>.hidden { display: none; }</style></head><body>
<section id="home-screen" class="hidden"><h1>识字大挑战</h1><button id="start-btn">开始挑战</button></section>
<section id="level-screen" class="hidden"><h2>选择关卡</h2><div id="level-grid"></div><button id="back-home-btn">返回主页</button></section>
<section id="game-screen" class="hidden">
  <div><span id="score-display">0</span></div>
  <div><span id="current-q">1</span> / <span id="total-q">10</span></div>
  <div><span id="current-word"></span></div>
  <div id="options-container"></div>
</section>
<section id="result-screen" class="hidden">
  <h2>${c.title}</h2>
  <span id="final-score">0</span>
  <p id="result-msg">太棒了！</p>
  <button id="replay-btn">
      再玩一次
  </button>
  <button id="home-btn">返回主页</button>
</section>
<script>
  const WORDS = ${JSON.stringify(words)};
  const CFG = ${JSON.stringify({ ...c, endAfter })};
  const $ = (id) => document.getElementById(id);
  let qi = CFG.startAt - 1, score = 0, answered = 0, answering = false;
  function show(name) {
    ['home', 'level', 'game', 'result'].forEach(s => $(s + '-screen').classList.toggle('hidden', s !== name));
  }
  function load() {
    answering = false;
    const q = WORDS[qi];
    $('current-q').textContent = qi + 1;
    $('total-q').textContent = CFG.total;
    $('current-word').textContent = q.word;
    const box = $('options-container');
    box.innerHTML = '';
    const opts = [1, 2, 3].map(k => WORDS[(qi + k) % WORDS.length].pinyin);
    opts.splice(qi % 4, 0, q.pinyin);
    opts.forEach(opt => {
      const b = document.createElement('button');
      b.className = 'option-btn';
      b.textContent = opt;
      b.onclick = () => handle(b, opt, q.pinyin);
      box.appendChild(b);
    });
  }
  function handle(btn, selected, correct) {
    if (answering) return;
    answering = true;
    const ok = selected === correct;
    if (ok) {
      btn.classList.add('correct');
      score++;
      $('score-display').textContent = score;
    } else {
      btn.classList.add('wrong');
      document.querySelectorAll('.option-btn').forEach(b => { if (b.textContent === correct) b.classList.add('correct'); });
    }
    answered++;
    if (!CFG.advance) return;
    setTimeout(() => {
      if (answered >= CFG.endAfter) { showResult(); return; }
      const jump = CFG.jumpTo[String(answered)];
      qi = jump ? jump - 1 : qi + 1;
      load();
    }, ok ? CFG.correctDelay : CFG.wrongDelay);
  }
  function showResult() {
    show('result');
    $('final-score').textContent = CFG.finalScore ?? score;
    $('result-msg').textContent = CFG.message ?? (score === CFG.total ? ${JSON.stringify(MSG_PERFECT)}
      : score >= CFG.total * 0.8 ? ${JSON.stringify(MSG_GOOD)} : ${JSON.stringify(MSG_TRY_AGAIN)});
  }
  $('replay-btn').onclick = () => { qi = 0; score = 0; answered = 0; $('score-display').textContent = 0; show('game'); load(); };
  $('home-btn').onclick = () => show('home');
  if (CFG.screen === 'game') { show('game'); load(); }
  else if (CFG.screen === 'result') { show('result'); $('final-score').textContent = CFG.finalScore ?? 0; $('result-msg').textContent = CFG.message ?? ''; }
  else show(CFG.screen);
</script></body></html>`;
}

let browser: Browser;
let page: Page;
before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });
beforeEach(async () => { page = await browser.newPage(); });
afterEach(async () => { await page.close(); });

const load = (cfg: Cfg = {}) => page.setContent(resultHtml(cfg));

/** 断言 p 以 DeterministicAssertion 拒绝（step 记 failed），且消息匹配 re。 */
async function rejectsAssertion(p: Promise<unknown>, re: RegExp): Promise<void> {
  await assert.rejects(p, (e: unknown) => {
    assert.ok(e instanceof DeterministicAssertion, `应抛 DeterministicAssertion，实际 ${(e as Error)?.constructor?.name}: ${(e as Error)?.message}`);
    assert.match((e as Error).message, re);
    return true;
  });
}

/** 断言 p 以普通 Error（不是 DeterministicAssertion；step 记 error）拒绝，且消息匹配 re。 */
async function rejectsUsageError(p: Promise<unknown>, re: RegExp): Promise<void> {
  await assert.rejects(p, (e: unknown) => {
    assert.ok(e instanceof Error && !(e instanceof DeterministicAssertion), `应抛普通 Error，实际 ${(e as Error)?.constructor?.name}`);
    assert.match((e as Error).message, re);
    return true;
  });
}

// --- 连答多题：通过 ---
test("依次答对全部 10 题：到结算页、满分", async () => {
  await load();
  const records = await result.answerAllCorrect(page, 10);
  assert.deepEqual(records.map((r) => r.question), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  assert.ok(records.every((r) => r.kind === "correct"));
  assert.deepEqual(records.map((r) => r.outcome), [...Array(9).fill("next"), "result"]);
  const vocab = checks.loadVocabulary();
  assert.ok(records.every((r) => vocab.get(r.word) === r.pinyin), "每题点的都该是题库里该字的拼音");
  await result.resultTitleIs(page, "挑战完成！");
  await result.finalScoreIs(page, "10");
  await result.resultMessageIs(page, MSG_PERFECT);
});

test("依次答错全部 10 题：0 分", async () => {
  await load();
  const records = await result.answerAllWrong(page, 10);
  assert.equal(records.length, 10);
  assert.ok(records.every((r) => r.kind === "wrong"));
  const vocab = checks.loadVocabulary();
  assert.ok(records.every((r) => vocab.get(r.word) !== r.pinyin), "每题点的都该不是正确拼音");
  await result.finalScoreIs(page, "0");
  await result.resultMessageIs(page, MSG_TRY_AGAIN);
});

test("先答对 8 题再答错 2 题：8 分、中间档评语", async () => {
  await load();
  const records = await result.answerInSequence(page, 8, 2);
  assert.deepEqual(records.map((r) => r.kind), [...Array(8).fill("correct"), "wrong", "wrong"]);
  assert.equal(records.at(-1)!.outcome, "result");
  await result.finalScoreIs(page, "8");
  await result.resultMessageIs(page, MSG_GOOD);
});

test("每题等到切题再答下一题", async () => {
  await load({ total: 3, correctDelay: 300 });
  const started = performance.now();
  await result.answerAllCorrect(page, 3);
  assert.ok(performance.now() - started >= 900, "三题各停留 0.3 秒才切题，连答不可能快于 0.9 秒");
  await result.finalScoreIs(page, "3");
});

test("只答一部分题：停在答题页", async () => {
  await load({ total: 10 });
  const records = await result.answerInSequence(page, 2, 1);
  assert.deepEqual(records.map((r) => r.outcome), ["next", "next", "next"]);
  await checks.progressIs(page, "4", "10");
  await checks.scoreIs(page, "2");
});

// --- 连答多题：用例写法错误（普通 Error，记 error） ---
test("全部答对：总题数与进度不符时失败", async () => {
  await load({ total: 8 });
  await rejectsAssertion(result.answerAllCorrect(page, 10), /本组应共 10 题，进度显示共 8 题.*#total-q/);
});

test("全部答对：没从第 1 题开始用是用例写法错误", async () => {
  await load({ startAt: 3 });
  await rejectsUsageError(result.answerAllCorrect(page, 10), /「依次答对全部 10 题」要在刚进入关卡、第 1 题时用，当前已是第 3 题/);
});

test("要答的题数超过剩余题数是用例写法错误", async () => {
  await load({ total: 3 });
  await rejectsUsageError(result.answerInSequence(page, 3, 1), /要答 4 题（答对 3 题、答错 1 题），但当前是第 1 题、共 3 题，只剩 3 题可答/);
});

test("答对与答错都是 0 是用例写法错误", async () => {
  await load();
  await rejectsUsageError(result.answerInSequence(page, 0, 0), /答对与答错的题数不能都是 0/);
});

// --- 连答多题：应用没达到期望（DeterministicAssertion，记 failed） ---
test("连答要求答题页已显示", async () => {
  await load({ screen: "home" });
  await rejectsAssertion(result.answerInSequence(page, 1, 0, 300), /答题页没有显示，无法作答：当前显示的是 主页.*#game-screen/);
});

test("作答后一直不切题时失败", async () => {
  await load({ advance: false });
  await rejectsAssertion(
    result.answerInSequence(page, 1, 0, 300),
    /答对第 1 题（「两」选 "liǎng"）后 1\.8 秒内没有自动进入下一题，也没有进入结算页，仍显示第 1 题（共 10 题/,
  );
});

test("没答完就进了结算页时失败", async () => {
  await load({ total: 5, endAfter: 2 });
  await rejectsAssertion(result.answerInSequence(page, 3, 0), /答完第 2 题就进入了结算页，还有 1 题没答（共 5 题/);
});

test("应用跳题时失败", async () => {
  await load({ jumpTo: { "1": 3 } });
  await rejectsAssertion(result.answerInSequence(page, 3, 0), /第 2 次作答前进度应显示第 2 题，实际显示第 3 题（已答 1 题，共 10 题/);
});

test("答完最后一题没进结算页时失败", async () => {
  await load({ total: 2, endAfter: 99 });
  await rejectsAssertion(result.answerAllCorrect(page, 2), /答完最后一题（第 2 题）后没有进入结算页，进度显示第 3 题/);
});

// --- 结算页判定 ---
test("结算页标题、最终得分、评语通过", async () => {
  await load({ screen: "result", finalScore: 10, message: MSG_PERFECT });
  await result.resultTitleIs(page, "挑战完成！");
  await result.finalScoreIs(page, "10");
  await result.resultMessageIs(page, MSG_PERFECT);
});

test("结算页标题不符时失败并带实际值", async () => {
  await load({ screen: "result", title: "Challenge Complete!" });
  await rejectsAssertion(result.resultTitleIs(page, "挑战完成！", 300), /结算页标题应为 "挑战完成！"，实际 "Challenge Complete!".*#result-screen h2/);
});

test("最终得分是整段匹配不是子串", async () => {
  await load({ screen: "result", finalScore: 10 });
  await rejectsAssertion(result.finalScoreIs(page, "1", 300), /最终得分应为 "1"，实际 "10".*#final-score/);
});

test("评语不符时失败并带实际值", async () => {
  await load({ screen: "result", message: MSG_GOOD });
  await rejectsAssertion(result.resultMessageIs(page, MSG_PERFECT, 300), /评语应为 "太厉害了！全对！🌟"，实际 "真棒！继续加油！✨".*#result-msg/);
});

test("结算页判定要求结算页已显示", async () => {
  await load({ screen: "game" });
  const re = /结算页没有显示：当前显示的是 答题页.*#result-screen/;
  await rejectsAssertion(result.resultTitleIs(page, "挑战完成！", 300), re);
  await rejectsAssertion(result.finalScoreIs(page, "0", 300), re);
  await rejectsAssertion(result.resultMessageIs(page, MSG_TRY_AGAIN, 300), re);
});

test("评语判定会等晚到的更新", async () => {
  await load({ screen: "result", message: "" });
  await page.evaluate((msg) => setTimeout(() => { document.getElementById("result-msg")!.textContent = msg; }, 200), MSG_PERFECT);
  await result.resultMessageIs(page, MSG_PERFECT, 2000);
});

// --- 真应用：选择器、真实文案、真实切题节奏 ---
async function enterGroup1(lang?: string): Promise<void> {
  await page.goto(APP_INDEX.href + (lang ? `?lang=${lang}` : ""));
  await page.click("#start-btn");
  await page.locator("#level-grid button").first().click();
}

test("真应用：全部答对到结算页，再玩一次回到第 1 题、得分清零", async () => {
  await enterGroup1();
  const records = await result.answerAllCorrect(page, 10);
  assert.equal(records.at(-1)!.outcome, "result");
  await result.resultTitleIs(page, "挑战完成！");
  await result.finalScoreIs(page, "10");
  await result.resultMessageIs(page, MSG_PERFECT);
  await hasVisibleButton(page, "再玩一次");
  await hasVisibleButton(page, "返回主页");
  await page.click("#replay-btn");
  await checks.progressIs(page, "1", "10");
  await checks.scoreIs(page, "0");
});

test("真应用：全部答错 0 分，返回主页", async () => {
  await enterGroup1();
  await result.answerAllWrong(page, 10);
  await result.finalScoreIs(page, "0");
  await result.resultMessageIs(page, MSG_TRY_AGAIN);
  await page.click("#home-btn");
  await hasVisibleButton(page, "开始挑战");
});

test("真应用：答对 8 题答错 2 题得 8 分", async () => {
  await enterGroup1();
  await result.answerInSequence(page, 8, 2);
  await result.finalScoreIs(page, "8");
  await result.resultMessageIs(page, MSG_GOOD);
});

test("真应用：英文界面下全部答对", async () => {
  await enterGroup1("en");
  await result.answerAllCorrect(page, 10);
  await result.resultTitleIs(page, "Challenge Complete!");
  await result.finalScoreIs(page, "10");
  await result.resultMessageIs(page, "Amazing! All correct! 🌟");
  await hasVisibleButton(page, "Play Again");
  await hasVisibleButton(page, "Back to Home");
});

test("真应用：答题页上判结算页要失败（结算页未显示）", async () => {
  await enterGroup1();
  await rejectsAssertion(result.finalScoreIs(page, "0", 800), /结算页没有显示：当前显示的是 答题页/);
});
