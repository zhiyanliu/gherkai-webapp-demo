# 演示 runbook（30 分钟）

演示按一条从 clone 开始、可逐段复制执行的 30 分钟时间线进行，覆盖安装 skill、三层输入与 agent 的产出、预检、本机后端运行、失败诊断、云端后端提交。**演示中不现场生成 feature 与 step**：一次生成需要 10 到 15 分钟，超出时间预算；演示只说明生成方式，并查看仓库中已有的产出。完整的生成步骤见文末「自行体验」一节，供读者自行执行。涉及 AI agent 的命令给出 Claude Code 与 Codex 两种写法，相同的命令只写一次。

## 演示前一天

以下准备不计入 30 分钟。

1. 安装与凭证（按 [gherkai 用户指南](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/getting-started.md)）：

   ```bash
   uv tool install --force --refresh 'gherkai[local,deploy-aws]'
   npm i -g @gherkai/worker-midscene@"$(gherkai --version | awk '{print $2}')"
   gherkai doctor                       # 本机后端：引擎、模型、AWS 身份都应为 ✓
   ngrok config check                   # 隧道：已配置 authtoken
   ```

2. AI agent（Claude Code 或 Codex）：主时间线不需要它在场，`gherkai skill install` 只是把 skill 文件装进项目目录；只有文末「自行体验」一节需要已安装并登录的 agent。

3. 云端后端（可选段使用）：部署方已将云端后端部署为与命令行相同的版本，并按 [云端后端演示的准备](./cloud-demo-preparation.md) 注册 variant `demo`。核对命令：

   ```bash
   gherkai doctor --backend cloud --prefix vfy- --region us-east-1
   gherkai deploy list-workers --prefix vfy- --region us-east-1
   ```

4. 预热一次，排除首次运行的冷启动，并记录墙钟时长供现场对照：

   ```bash
   cd ~ && git clone https://github.com/zhiyanliu/gherkai-webapp-demo.git && cd gherkai-webapp-demo
   (cd app && python3 -m http.server 8080 > /tmp/demo-app.log 2>&1 &)
   gherkai run features/level-select.feature --expose-local http://localhost:8080 --region us-east-1
   rm -rf ~/gherkai-webapp-demo                     # 预热后删除目录，演示时重新 clone
   ```

5. 终端布局：一个终端用于讲解与运行，应用的静态服务在后台运行；另开一个浏览器窗口查看应用与报告。

## 时间线

命令本身的执行时间合计约 10 分钟，其中两次本机运行各约 4 分钟；其余时间用于讲解。

| 时间 | 段 |
|---|---|
| 0:00 | 开场：问题与主张 |
| 2:00 | 从 clone 起：环境、项目形状、安装 skill |
| 5:00 | 三层输入与 agent 的产出 |
| 10:00 | 预检与本机后端运行 |
| 14:00 | 失败诊断与处置 |
| 19:00 | 云端后端提交 |
| 21:00 | 确定性 step 的代码与验收 |
| 25:00 | 云端结果 |
| 28:00 | 收尾 |

### 0:00 开场

不执行命令。要点：用例写在 `.feature` 文件中；每一步交给 AI 判定，还是命中项目注册的确定性 step 由代码判定，由工具按步派发；浏览器运行在云端；QA 负责测试设计，agent 负责用例与代码，人负责验收与决策。

### 2:00 从 clone 起（环境、项目形状、安装 skill）

```bash
cd ~ && git clone https://github.com/zhiyanliu/gherkai-webapp-demo.git && cd gherkai-webapp-demo
gherkai --version
gherkai doctor
ls
(cd app && python3 -m http.server 8080 > /tmp/demo-app.log 2>&1 &)
```

安装 skill（两种 agent 二选一，或 `--agent all`）：

```bash
gherkai skill install --agent claude-code --pointer yes     # Claude Code：装到 .claude/skills/，提示行写进 CLAUDE.md
gherkai skill install --agent codex --pointer yes           # Codex：装到 .agents/skills/，提示行写进 AGENTS.md
```

讲解：`app/` 是被测应用，`features/` 每个功能域一份，`steps/` 是两个引擎成对的确定性 step；skill 与命令行版本一致，由每位成员在本机安装，不提交到仓库。

### 5:00 三层输入与 agent 的产出

```bash
sed -n 1,40p .claude/skills/gherkai/SKILL.md        # 工具层：skill（Codex 装在 .agents/skills/gherkai/SKILL.md）
cat docs/ui-testing-conventions.md                  # 项目层：约定
cat docs/briefs/level-select.md                     # 任务层：简报
cat features/level-select.feature                   # agent 据简报产出的 feature
```

讲解：对任何一份简报都成立的内容不属于简报，归项目约定；工具本身的用法不写进项目约定，由 skill 承担。仓库中的四份 feature 与全部 step 均由 agent 按简报生成、经人验收后提交；将简报与 feature 并排对照，双引号内的自然语言是 AI 步，`关卡按钮有 "8" 个` 这类是确定性 step。期望只来自需求，查看应用只为定位元素。生成的步骤与提示词见文末「自行体验」一节，演示中不执行。

### 10:00 预检与本机后端运行

```bash
gherkai plan features/*.feature                     # 18 个 job；带「← 确定性」标注的步走代码，其余走 AI
gherkai run features/result.feature --expose-local http://localhost:8080 --region us-east-1
```

运行约 4 分钟。等待期间讲解输出中的三点：「隧道已建立」一行表示本机应用经隧道供云端浏览器访问，凭据每次运行更换；`result-replay-and-home` 这个 job 是一条 `@scope` 接续链，三条 scenario 在同一浏览器会话中串行执行；其余 job 各开一个会话并行执行。结束后打开报告 `reports/<run_id>/index.html`。

### 14:00 失败诊断与处置

预埋一个应用缺陷：「再玩一次」不再清零得分。只修改一行，演示后还原。

```bash
sed -i.bak 's/^\(\s*\)STATE.score = 0;$/\1\/\/ STATE.score = 0;/' app/index.html
gherkai run features/result.feature --scope result-replay-and-home --expose-local http://localhost:8080 --region us-east-1
```

约 4 分钟。接续链三条 scenario 中第一条通过，第二条「再玩一次回到第 1 题且得分清零」在确定性 step `得分为 "0"` 判否，第三条继续执行并通过。失败消息形如「得分应为 "0"，实际 "10"（页面 …，选择器 #score-display）」。读取证据并处置：

```bash
gherkai explain <run_id>
mv app/index.html.bak app/index.html               # 还原应用
```

讲解四种处置：修改断言措辞、改为确定性 step、更换引擎、认定为应用缺陷并报出。本例属于第四种。

### 19:00 云端后端提交

```bash
gherkai submit features/level-select.feature --backend cloud --prefix vfy- --region us-east-1 \
  --worker-variant demo --expose-local http://localhost:8080
```

命令立即返回 run_id，后续步骤需要使用它。讲解：worker 与浏览器都在云端，本机只持有隧道；云端运行的确定性 step 来自 variant `demo` 的镜像，而不是本机的 `steps/`，镜像的构建与注册见 [云端后端演示的准备](./cloud-demo-preparation.md)。

### 21:00 确定性 step 的代码与验收

```bash
cat steps/level_select.py                           # 注册薄壳：模式、说明、示例
sed -n 1,60p steps/_level_select.py                 # 判定逻辑：带等待、失败消息带现场
gherkai list-deterministic --engine novaact
gherkai list-deterministic --engine midscene
uv sync && uv run playwright install chromium && uv run pytest steps/test_level_select.py -q   # 本地单测，可选
```

讲解：QA 验收 feature 文本与预检结果，不阅读代码；测试开发 review step 代码，关注四点：两引擎成对、判定带等待与超时、失败消息带现场信息、判定逻辑与注册分离并配有单测。

### 25:00 云端结果

```bash
gherkai status <run_id> --wait --backend cloud --prefix vfy- --region us-east-1
gherkai explain <run_id> --backend cloud --prefix vfy- --region us-east-1
```

讲解：`status --wait` 的退出码即判定结果；报告位于 S3；`explain` 输出中隧道地址的凭据显示为 `***`。

### 28:00 收尾

费用与速度：运行输出中每个 job 的 token 数与墙钟时长；确定性 step 不产生模型费用、毫秒级完成。分工：QA 编写简报并验收、测试开发维护 `steps/`、部署方维护云端后端。采用路径：先在本机后端接入一个功能域，再使用云端后端。

## 应急

- 本机运行判否但原因不是预埋的缺陷：以它作为 14:00 段的素材，`explain` 之后按四种处置讲解。
- 隧道建立失败：执行 `ngrok config check`；仍失败则跳过本机运行，只讲预检与云端段。
- 云端结果到 25:00 仍未到终态：先收尾，`status --wait` 放在最后执行。
- 模型服务偶发 5xx 或 AI 判定抖动属于正常现象，重新运行对应的 job：`gherkai run <feature> --scope <scope_id> --expose-local http://localhost:8080 --region us-east-1`。

## 自行体验：让 agent 按简报生成 feature 与 step

演示中不执行本节。读者自行执行时，先移开仓库中已有的产出，否则 agent 会直接读取已有的 feature 与 step；结束后用 git 还原。以选关页为例，agent 需要 10 到 15 分钟。

```bash
cd ~/gherkai-webapp-demo
git rm -rq features steps                           # 移开已有产出（只影响工作区与暂存区，不提交）
gherkai skill install --agent claude-code --pointer yes     # 或 --agent codex
claude                                              # Codex 用 codex
```

进入交互界面后输入：

```text
按 docs/briefs/level-select.md 写用例与确定性 step，按 docs/ui-testing-conventions.md 的约束与交付物交付。先别真跑。
```

agent 交付后按项目约定验收，再与仓库中的版本对照：

```bash
cat features/level-select.feature
gherkai plan features/level-select.feature
gherkai list-deterministic --engine novaact
gherkai list-deterministic --engine midscene
git diff HEAD -- features/level-select.feature      # 与已提交版本的差异
git checkout HEAD -- features steps && git clean -fd features steps   # 还原仓库
```

本仓库四份 feature 的生成用时与两种 agent 的操作差异见 [QA 团队的工作方法](./qa-practice-with-gherkai.md) 第 5 节与第 9 节。

## 演示后

```bash
pkill -f "http.server 8080"                        # 停应用
rm -rf ~/gherkai-webapp-demo                       # 删除演示目录，下次重新 clone
```
