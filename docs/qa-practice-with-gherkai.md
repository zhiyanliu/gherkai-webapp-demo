# 用 gherkai 做 UI 测试：QA 团队的工作方法

这份文档讲的是方法：一个 QA 团队怎样把需求变成可运行的用例，怎样给 AI agent 派活，怎样验收它的产出，怎样在失败时修正。命令与选项的说明不在这里，在 [gherkai 用户指南](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/README.md)。本仓库就是按这套方法组织的一个项目，可以对照着看。

## 1. 分工

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| QA / 测试工程师 | 读需求、切功能域、圈出必须精确的检查、给 agent 写测试任务简报、review 用例文本、发起运行、读结果 | 不写代码 |
| 测试开发 | 维护 `steps/` 里的确定性 step 代码、本地单测、把 steps 带到云端镜像 | 不替 QA 决定测什么 |
| 部署方 | 部署与维护团队共享的云端后端 | 不参与写用例 |
| AI agent（装了 gherkai skill 的 Claude Code、Codex 等） | 按简报写 feature 与确定性 step、自查注册与预检、读失败证据、给出修正建议并汇报 | 不自行决定真跑、不改需求口径 |

AI agent 不是替 QA 决定测什么的人，它替 QA 做施工：把测试设计变成 Gherkin 与代码，并用工具核对。测什么、精确到什么程度，仍是 QA 的判断。

## 2. 一次性立项

项目开始时做一次，之后每张简报都不必重复交代：

1. 装命令行与本机 worker（`uv tool install 'gherkai[local]'`，Midscene 引擎另装 `npm i -g @gherkai/worker-midscene`）。
2. 把 gherkai 的 agent skill 装进项目：`gherkai skill install --agent all`。它会问是否把一行提示写进项目的 `CLAUDE.md` 与 `AGENTS.md`，答是。
3. 写项目约定，放在 agent 一定会读到的地方（本仓库是 [docs/testing-conventions.md](./testing-conventions.md)，`CLAUDE.md` 与 `AGENTS.md` 各指向它）：用例目录布局、tag 约定、scope 命名、被测地址、界面语言、默认不真跑。
4. 确认被测应用有一个稍后运行时可达的地址。本机应用用 `--expose-local` 起隧道即可，不必先部署。

## 3. QA 的备料

好用例来自好输入。给 agent 派活之前 QA 准备三样：

**需求文档作唯一事实源。** 用例的每条期望都能在需求里找到出处。需求含糊的地方先问产品，不让 agent 猜。本仓库的需求是 [docs/product-requirements.md](./product-requirements.md)。

**按功能域切分。** 一个功能域一份 feature 文件，切分依据是需求文档的功能条目，与组织 Playwright 或手工用例的方式一样。每条需求的验收要点展开成 scenario。工具对切分没有要求，它只规定三件事：用例写在 `.feature` 里；一条 scenario 是一个独立判定单元；需要接着上一条页面状态的用 `@scope` 编进同一个浏览器会话。

**圈出必须精确的检查。** 每条 scenario 的期望分两类，判据如下：

| 走确定性 step（代码判定） | 交给 AI 判定 |
|---|---|
| 数值、计数、精确文本、页面标题、地址 | 页面整体形态、视觉状态（高亮、颜色）、语义判断（「看起来像出错页」） |
| 必须可复现、结果不能抖动 | 一次性检查、页面结构常变 |
| 出现频次高（每条 scenario 都重复、参数化每行都做） | 用自然语言更好表达的动作 |
| 答案不在页面上、要查数据（如题库） | |

成本与速度是判据的一部分：AI 步每判一次调用一次模型，一步几秒到几十秒；确定性 step 零模型费用、毫秒级完成。连答十题这类重复动作，交给 AI 慢且贵，写成确定性 step 是自然选择。

**界面语言也是事实。** 被测界面是什么语言、有没有多语言，写进简报。引擎怎么选是工具的事：agent 会按界面语言给 scenario 标引擎并说明理由。

## 4. 给 agent 派活：测试任务简报

派活用简报，不用一句话。简报是 QA 平时给同事派活时说的那几句话，写成固定的小标题：功能域与对应需求、被测地址与界面语言、要覆盖的场景、必须精确的检查、约束、交付。模板在 [docs/test-brief-template.md](./test-brief-template.md)，可以直接复制；本仓库每个功能域的简报在 [docs/briefs/](./briefs/)。

一张简报对应一个功能域，产出一份 feature 文件。简报固定形状的意义是让产出可预期、可 review，团队里换谁写都得到同一形状的用例。

## 5. 验收 agent 的产出

QA 验收三样，都不需要读代码：

- **feature 文本**：像不像一条能拿给产品确认的验收用例；导航步写的是需求里的地址；AI 断言是页面级陈述而不是子串规则；精确检查落在了确定性 step 上。
- **预检结果**：`gherkai plan` 的输出，每个 step 标了走确定性还是 AI，没有冲突标记；job 数就是这次运行要开的浏览器会话数，也就是费用规模。
- **注册清单**：`gherkai list-deterministic --engine <引擎>` 两个引擎各一份，新写的 step 都在。

确定性 step 的代码质量归测试开发 review：判定带等待与超时、失败消息带现场、判定逻辑与注册分离、有本地单测。

## 6. 运行与修正

运行由 QA 发起。本机用 `gherkai run`，团队共享的云端后端用 `gherkai submit` 加 `gherkai status --wait`。被测应用只在本机时加 `--expose-local <地址>`，运行期间本机保持开机联网。

有用例没过，第一个命令是 `gherkai explain <run_id>`：它把判定、原因、模型看见了什么、截图在哪拼成一份别人能复现的证据。然后四选一：

1. 断言写法有歧义：改 feature 那一步的措辞。
2. 精确检查被 AI 判抖：落到确定性 step。
3. 非英文界面上文本断言判否：换引擎路由。
4. 复投三票一致判否：认定被测应用的问题，报 bug。

每一种处置都要写进汇报。改断言、换引擎都动了验收口径，不说等于悄悄放宽了用例。让 agent 做修正时，它会按同样的顺序处置并汇报。

## 7. 沉淀

- 确定性 step 按主题分文件放在 `steps/`，判定逻辑放 `_` 前缀的辅助模块并配单测，两个引擎成对维护。
- 用了云端后端的团队，改了 `steps/` 要重新构建 worker 镜像并推送，云端读的是镜像里那份。
- CI 接 `gherkai run` 的退出码，或 `submit` 之后 `status --wait` 的退出码。

## 8. 两种 agent 的差别

Claude Code 读项目里的 `.claude/skills/`，Codex 读 `.agents/skills/`，`gherkai skill install --agent all` 两处都装。项目约定分别经 `CLAUDE.md` 与 `AGENTS.md` 进入两者的上下文。简报的给法一样：把简报全文作为一次对话的输入。

（两种 agent 在本项目上各走一遍之后，操作差异与注意事项补在这里。）
