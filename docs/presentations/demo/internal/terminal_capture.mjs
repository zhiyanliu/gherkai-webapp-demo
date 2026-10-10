/**
 * Replay an existing asciicast in a wider xterm, then capture its terminal grid.
 * Uses the xterm and Playwright already bundled with the workspace runtime.
 * No test, shell command from the recording, or network service is executed.
 */
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {createRequire} from 'node:module';
import {homedir} from 'node:os';
import {fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const runtime = process.env.DEMO_NODE_MODULES || path.join(homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const build = path.resolve(process.env.DEMO_BUILD_DIR || path.join(path.dirname(fileURLToPath(import.meta.url)), 'work'));
const {chromium} = require(path.join(runtime, 'playwright'));
const vendor = path.join(runtime, 'playwright-core/lib/vite/traceViewer');
const assets = await fs.readdir(path.join(vendor, 'assets'));
const rootFiles = await fs.readdir(vendor);
const moduleName = assets.find(x => /^xtermModule-.*\.js$/.test(x));
const cssName = rootFiles.find(x => /^xtermModule\..*\.css$/.test(x));
if (!moduleName || !cssName) throw new Error('Bundled xterm resources were not found.');

const batch = process.argv[2] ? JSON.parse(await fs.readFile(process.argv[2], 'utf8')) : null;
const work = path.resolve(batch?.work || path.join(build, 'terminal-focus'));
await fs.mkdir(work, {recursive: true});
const source = path.join(build, 'capture/recording/fault/explain.cast');
const records = (await fs.readFile(source, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
const [header, ...events] = records;
const output = events.filter(e => e[1] === 'o');
const columns = 152;
const document = `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="/vendor/${cssName}"><style>
html,body{margin:0;background:#09130f}#terminal{padding:0;width:max-content}
.xterm-cursor-layer,.xterm-cursor{visibility:hidden!important}
.xterm-viewport::-webkit-scrollbar{display:none}
</style></head><body><div id="terminal"></div><script type="module">
import bundle from '/vendor/assets/${moduleName}';
const terminal = new bundle.Terminal({
 cols:${columns}, rows:${header.height}, scrollback:2000, fontSize:20, lineHeight:1,
 fontFamily:'Menlo, "Hiragino Sans GB", monospace',
 letterSpacing:0, cursorBlink:false, cursorInactiveStyle:'none',
 allowProposedApi:true, convertEol:false,
 theme:{
  background:'#09130f',foreground:'#a7efb1',cursor:'#a7efb1',
  black:'#648071',red:'#ff8eaa',green:'#94edaa',yellow:'#edce83',
  blue:'#91bafa',magenta:'#d6a9ef',cyan:'#80d9d2',white:'#bad3c4',
  brightBlack:'#87a593',brightRed:'#ff8eaa',brightGreen:'#b5ffc1',
  brightYellow:'#ffe09a',brightBlue:'#b1d0ff',brightMagenta:'#edc6ff',
  brightCyan:'#a4eee7',brightWhite:'#dbfbe3'
 }
});
terminal.open(document.getElementById('terminal'));
window.term=terminal;
window.writeTerminal=data=>new Promise(resolve=>terminal.write(data,resolve));
// Keep CJK punctuation on the same cell grid as Latin text. The DOM renderer's
// fallback-font measurements can otherwise give punctuation excess width.
window.alignTerminalGrid=()=>{
 const bounds=document.querySelector('.xterm-screen').getBoundingClientRect();
 const cellWidth=bounds.width/terminal.cols;
 const buffer=terminal.buffer.active;
 const rows=document.querySelector('.xterm-rows').children;
 for(let row=0;row<rows.length;row++){
  const line=buffer.getLine(buffer.viewportY+row);
  let column=0;
  for(const span of rows[row].children){
   let seen='',cells=0;
   while(seen.length<span.textContent.length&&column<terminal.cols){
    const cell=line.getCell(column);
    const width=Math.max(1,cell.getWidth());
    seen+=cell.getChars()||' ';
    cells+=width;
    column+=width;
   }
   if(seen!==span.textContent)throw new Error('Terminal text and cell grid disagree.');
   span.style.display='inline-block';
   span.style.width=(cells*cellWidth)+'px';
   span.style.boxSizing='border-box';
  }
 }
};
await document.fonts.ready;
window.terminalReady=true;
</script></body></html>`;

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/') {
      res.setHeader('Content-Type', 'text/html; charset=utf-8');
      res.end(document);
      return;
    }
    if (!url.pathname.startsWith('/vendor/')) {
      res.writeHead(404).end();
      return;
    }
    const file = path.resolve(vendor, decodeURIComponent(url.pathname.slice('/vendor/'.length)));
    if (!file.startsWith(vendor + path.sep)) {
      res.writeHead(403).end();
      return;
    }
    res.setHeader('Content-Type', file.endsWith('.css') ? 'text/css' : 'text/javascript');
    res.end(await fs.readFile(file));
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const errors = [];
let browser;
try {
  browser = await chromium.launch({
    headless: true,
    executablePath: '/Users/lzy/Library/Caches/ms-playwright/chromium_headless_shell-1194/chrome-mac/headless_shell',
  });
  const page = await browser.newPage({viewport: {width: 2048, height: 1000}, deviceScaleFactor: 2});
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.waitForFunction(() => window.terminalReady, null, {timeout: 10000});
  if (batch) {
    const results = [];
    for (const job of batch.jobs) {
      await page.evaluate(({cols,rows,fontSize=22}) => {
        window.term.reset();
        window.term.options.fontSize=fontSize;
        window.term.options.lineHeight=1.08;
        window.term.resize(cols,rows);
      },job);
      await page.evaluate(data=>window.writeTerminal(data),job.content);
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      await page.evaluate(()=>window.alignTerminalGrid());
      const metrics=await page.evaluate(()=>{
        const b=window.term.buffer.active;
        const bounds=document.querySelector('.xterm-screen').getBoundingClientRect();
        return {cols:window.term.cols,rows:window.term.rows,width:bounds.width,height:bounds.height,
          viewportY:b.viewportY,lines:Array.from({length:b.length},(_,i)=>b.getLine(i).translateToString(true))};
      });
      if(metrics.viewportY!==0)throw new Error('Batch terminal overflows vertically: '+job.name);
      await page.locator('.xterm-screen').screenshot({path:path.join(work,job.name+'.png')});
      results.push({name:job.name,...metrics});
    }
    if(errors.length)throw new Error(errors.join('\n'));
    await fs.writeFile(path.join(work,'terminal-metrics.json'),JSON.stringify(results,null,2));
    console.log(`Captured ${results.length} terminal views from recorded events and source-file excerpts.`);
  } else {
  await page.evaluate(data => window.writeTerminal(data), output[0][2]);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  const screen = page.locator('.xterm-screen');
  await screen.screenshot({path: path.join(work, 'terminal-command-grid.png')});

  for (const event of output.slice(1)) {
    await page.evaluate(data => window.writeTerminal(data), event[2]);
  }
  await page.evaluate(() => {
    window.term.scrollToBottom();
    return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await page.evaluate(() => window.alignTerminalGrid());
  const grid = await page.evaluate(() => {
    const b = window.term.buffer.active;
    const bounds = document.querySelector('.xterm-screen').getBoundingClientRect();
    const lines = Array.from({length: b.length}, (_, i) => b.getLine(i).translateToString(true));
    const scenario = lines.findIndex(x => x.includes('scenario features/result.feature:20'));
    const failure = lines.findIndex(x => x.includes('step 3  Then 得分为 "0"'));
    const end = lines.findIndex((x, i) => i > scenario && x.includes('scenario features/result.feature:28'));
    let messagePrefixEnd = -1;
    const message = b.getLine(failure + 1);
    for (let column = 0; column < window.term.cols; column++) {
      if (message.getCell(column)?.getChars() === '（') {
        messagePrefixEnd = column;
        break;
      }
    }
    const messageRow = document.querySelector('.xterm-rows')?.children[failure + 1 - b.viewportY];
    const messageSpan = messageRow && Array.from(messageRow.children).find(span => span.textContent === '（');
    const messagePrefixEndPx = messageSpan ? messageSpan.getBoundingClientRect().x - bounds.x : null;
    const wrappedRows = Array.from({length:b.length},(_,i)=>i).filter(i=>b.getLine(i).isWrapped);
    const rowBounds = Array.from(document.querySelector('.xterm-rows').children, row =>
      Math.max(0,...Array.from(row.children, span => span.textContent.trim()
        ? span.getBoundingClientRect().right - bounds.x : 0)));
    return {
      cols:window.term.cols,rows:window.term.rows,
      width:bounds.width,height:bounds.height,rowHeight:bounds.height/window.term.rows,
      viewportY:b.viewportY,scenario,failure,end,messagePrefixEnd,messagePrefixEndPx,
      wrappedRows,maxRowWidth:Math.max(...rowBounds),lines,
    };
  });
  if (grid.cols !== columns || grid.rows !== header.height || grid.failure < 0 || !grid.messagePrefixEndPx) {
    throw new Error('Terminal geometry or the expected failure row did not match the recording.');
  }
  if (grid.wrappedRows.length || grid.maxRowWidth > grid.width) {
    throw new Error('Terminal capture still contains wrapped or clipped output.');
  }
  await screen.screenshot({path: path.join(work, 'terminal-output-grid.png')});
  await fs.writeFile(path.join(work, 'terminal-grid.json'), JSON.stringify({
    source:path.relative(process.cwd(),source),
    method:'Original ANSI events replayed through a wider xterm; screenshot of its terminal grid. No output text or explicit newlines changed.',
    original_columns:header.width,replay_columns:columns,terminal_rows_preserved:true,
    theme:'Near-black background, soft luminous green text, distinct ANSI status colors',
    line_height:1,device_scale_factor:2,
    first_output_seconds:output[1][0],
    grid,errors,
  },null,2));

  if (errors.length) throw new Error(errors.join('\n'));
  console.log(`Captured CLI grid (${grid.cols} × ${grid.rows}) for the failure focus.`);
  }
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
