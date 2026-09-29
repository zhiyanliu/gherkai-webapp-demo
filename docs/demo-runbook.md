# 演示 runbook（30 分钟）

本页给演示者使用：一条从零开始、可逐段复制执行的时间线，覆盖安装 skill、agent 按简报写用例、预检、本机后端运行、失败诊断、云端后端提交。命令分两组终端；涉及 AI agent 的命令给出 Claude Code 与 Codex 两种写法，相同的只写一次。

## 演示前一天

以下准备不计入 30 分钟。演示机可以是本机，也可以是经 ssh 登录的跳板机。

1. 安装与凭证（按 [gherkai 用户指南](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/getting-started.md)）：

   ```bash
   uv tool install --force --refresh 'gherkai[local,deploy-aws]'
   npm i -g @gherkai/worker-midscene@"$(gherkai --version | awk '{print $2}')"
   gherkai doctor                       # 本机后端：引擎、模型、AWS 身份都应为 ✓
   ngrok config check                   # 隧道：已配置 authtoken
   ```

2. AI agent：Claude Code 或 Codex 已登录并能正常对话。

3. 两个工作目录。`gherkai-webapp-demo` 是完整项目，用来运行；`gherkai-webapp-demo-start` 检出 `demo-start` 分支，没有 `features/` 与 `steps/`，供 agent 从零写用例：

   ```bash
   cd ~
   git clone https://github.com/zhiyanliu/gherkai-webapp-demo.git
   git clone -b demo-start https://github.com/zhiyanliu/gherkai-webapp-demo.git gherkai-webapp-demo-start
   ```

4. 云端后端（可选段用）：部署方已把云端后端部署到与命令行相同的版本，并按 [云端后端演示的准备](./cloud-demo-preparation.md) 注册好 variant `demo`。核对：

   ```bash
   cd ~/gherkai-webapp-demo
   gherkai doctor --backend cloud --prefix vfy- --region us-east-1
   gherkai deploy list-workers --prefix vfy- --region us-east-1
   ```

5. 预热一次，排除首次运行的冷启动，并记下墙钟供现场对照：

   ```bash
   cd ~/gherkai-webapp-demo/app && (python3 -m http.server 8080 > /tmp/demo-app.log 2>&1 &)
   cd ~/gherkai-webapp-demo && gherkai run features/level-select.feature --expose-local http://localhost:8080 --region us-east-1
   ```

6. 经 ssh 演示跳板机时，本机浏览器要看到被测应用，另开一个端口转发：`ssh -L 8080:localhost:8080 <跳板机>`，然后打开 `http://localhost:8080`。

7. 终端布局：终端 A 用于讲解与运行（完整项目目录），终端 B 用于 agent（从零目录），应用的静态服务放在后台。

## 时间线

| 时间 | 段 | 终端 |
|---|---|---|
| 0:00 | 开场：问题与主张 | 无 |
| 2:00 | 环境与项目形状 | A |
| 4:00 | 安装 skill，agent 按简报开始写用例 | B |
| 7:00 | 三层输入：skill、项目约定、简报 | A |
| 10:00 | 预检与本机后端运行 | A |
| 14:00 | 失败诊断与处置 | A |
| 19:00 | 云端后端提交 | A |
| 20:00 | 验收 agent 的交付 | B、A |
| 25:00 | 云端结果 | A |
| 28:00 | 收尾 | 无 |

### 0:00 开场

不执行命令。要点：用例写在 `.feature` 里，一步交给 AI、还是命中项目注册的确定性 step 走代码，由工具按步派发；浏览器在云端；QA 写测试设计，agent 写用例与代码，人验收与决策。

### 2:00 环境与项目形状（终端 A）

```bash
cd ~/gherkai-webapp-demo
gherkai --version
gherkai doctor
ls
cat features/quiz.feature
```

讲解：`app/` 是被测应用，`features/` 一个功能域一份，`steps/` 是两个引擎成对的确定性 step。`quiz.feature` 里带双引号的自然语言是 AI 步，`得分为 "1"`、`进度显示 "1 / 10"` 这类是确定性 step。

### 4:00 安装 skill，agent 开始写用例（终端 B）

```bash
cd ~/gherkai-webapp-demo-start
ls                                   # 只有 app/、docs/，没有 features/ 与 steps/
cat docs/briefs/level-select.md      # 这次要交给 agent 的简报
```

安装 skill（两种 agent 二选一，或 `--agent all`）：

```bash
gherkai skill install --agent claude-code --pointer yes     # Claude Code：装到 .claude/skills/，提示行写进 CLAUDE.md
gherkai skill install --agent codex --pointer yes           # Codex：装到 .agents/skills/，提示行写进 AGENTS.md
```

启动 agent 并交给它简报（进入交互界面后粘贴下面这段话）：

```bash
claude        # Claude Code
codex         # Codex
```

```text
按 docs/briefs/level-select.md 写用例与确定性 step，按 docs/ui-testing-conventions.md 的约束与交付物交付。先别真跑。
```

agent 需要 10 到 15 分钟，让它在终端 B 继续，回到终端 A。

### 7:00 三层输入（终端 A）

```bash
cd ~/gherkai-webapp-demo
sed -n 1,40p .claude/skills/gherkai/SKILL.md        # 工具层：skill（Codex 装在 .agents/skills/gherkai/SKILL.md）
cat docs/ui-testing-conventions.md                  # 项目层：约定
cat docs/briefs/level-select.md                     # 任务层：简报
```

讲解：放到任何一份简报里都成立的内容不属于简报，归项目约定；工具本身的用法不写进项目约定，交给 skill。期望只来自需求，看应用只为定位元素。

### 10:00 预检与本机后端运行（终端 A）

```bash
gherkai plan features/*.feature                     # 18 个 job；带「← 确定性」标注的步走代码，其余走 AI
gherkai run features/result.feature --expose-local http://localhost:8080 --region us-east-1
```

运行约 4 分钟。等待期间讲解输出里的三件事：「隧道已建立」一行（本机应用经隧道给云端浏览器访问，凭据每次一换）；`result-replay-and-home` 这个 job 是一条 `@scope` 接续链，三条 scenario 在同一浏览器会话里串行；其余 job 各开一个会话并行。结束后打开报告 `reports/<run_id>/index.html`。

### 14:00 失败诊断与处置（终端 A）

预埋一个应用缺陷：「再玩一次」不再清零得分。只改一行、演示后还原。

```bash
sed -i.bak 's/^\(\s*\)STATE.score = 0;$/\1\/\/ STATE.score = 0;/' app/index.html
gherkai run features/result.feature --scope result-replay-and-home --expose-local http://localhost:8080 --region us-east-1
```

约 4 分钟（实测 223 秒：接续链三条中第一条通过、第二条判否、第三条继续通过）。判否落在「再玩一次回到第 1 题且得分清零」的确定性 step `得分为 "0"`，失败消息形如「得分应为 "0"，实际 "10"（页面 …，选择器 #score-display）」。读证据并处置：

```bash
gherkai explain <run_id>
mv app/index.html.bak app/index.html               # 还原应用
```

讲解四种处置：改断言措辞、落成确定性 step、换引擎、认定应用缺陷并报出。这一例是第四种。若要展示 agent 参与修正，在终端 B 的 agent 空闲时输入：

```text
gherkai run 报告 <run_id> 判否，请用 gherkai explain 读证据，判断是用例问题还是应用问题，给出处置建议，先别真跑。
```

### 19:00 云端后端提交（终端 A）

```bash
gherkai submit features/level-select.feature --backend cloud --prefix vfy- --region us-east-1 \
  --worker-variant demo --expose-local http://localhost:8080
```

命令立刻返回 run_id，记下它。讲解：worker 与浏览器都在云端，本机只持有隧道；云端运行的确定性 step 来自 variant `demo` 的镜像，不是本机的 `steps/`。

### 20:00 验收 agent 的交付（终端 B、A）

agent 交付后按项目约定验收：feature 文本、预检、两个引擎的注册清单。

```bash
cd ~/gherkai-webapp-demo-start
cat features/level-select.feature
gherkai plan features/level-select.feature
gherkai list-deterministic --engine novaact
gherkai list-deterministic --engine midscene
```

对照完整项目里的同一份 feature（终端 A：`cat ~/gherkai-webapp-demo/features/level-select.feature`）。agent 尚未交付时，先讲完整项目里的版本与 agent 已产出的部分，交付后再回来。

### 25:00 云端结果（终端 A）

```bash
gherkai status <run_id> --wait --backend cloud --prefix vfy- --region us-east-1
gherkai explain <run_id> --backend cloud --prefix vfy- --region us-east-1
```

讲解：`status --wait` 的退出码就是判定；报告在 S3；`explain` 里隧道地址的凭据显示为 `***`。

### 28:00 收尾

费用与速度：运行输出里每个 job 的 token 数与墙钟；确定性 step 零模型费用、毫秒级。分工：QA 写简报与验收、测试开发维护 `steps/`、部署方维护云端后端。采用路径：先在本机后端接一个功能域，再上云端后端。

## 应急

- agent 到 20:00 仍未交付：跳过 20:00 段的对照，改为展示完整项目的 feature 与 `plan`，收尾时再看 agent 的产出。
- 本机运行判否但不是预埋的缺陷：直接用它做 14:00 段的素材，`explain` 后按四种处置讲。
- 隧道建立失败：`ngrok config check`；仍失败则跳过本机运行，改为只讲预检与云端段。
- 云端结果到 25:00 仍未终态：先收尾，`status --wait` 放到最后。
- 一次运行里模型服务偶发 5xx 或 AI 判定抖动属于正常现象，重新运行对应 job：`gherkai run <feature> --scope <scope_id> --expose-local http://localhost:8080 --region us-east-1`。

## 演示后

```bash
pkill -f "http.server 8080"                        # 停应用
rm -rf ~/gherkai-webapp-demo/reports ~/gherkai-webapp-demo-start/reports
cd ~/gherkai-webapp-demo-start && git checkout -- . && git clean -fd     # 丢弃 agent 的产出，下次再从零开始
```
