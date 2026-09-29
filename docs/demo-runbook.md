# 演示 runbook（30 分钟）

本页给演示者使用：一条从 clone 开始、可逐段复制执行的时间线，覆盖安装 skill、三层输入与 agent 的产出、预检、本机后端运行、失败诊断、云端后端提交。**演示中不现场生成 feature 与 step**：生成要 10 到 15 分钟，放不进 30 分钟；演示只讲生成方式并看仓库里已有的产出。生成的完整步骤在文末「自行体验」一节，供读者自己执行。涉及 AI agent 的命令给出 Claude Code 与 Codex 两种写法，相同的只写一次。

## 演示前一天

以下准备不计入 30 分钟。演示机可以是本机，也可以是经 ssh 登录的跳板机。

1. 安装与凭证（按 [gherkai 用户指南](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/getting-started.md)）：

   ```bash
   uv tool install --force --refresh 'gherkai[local,deploy-aws]'
   npm i -g @gherkai/worker-midscene@"$(gherkai --version | awk '{print $2}')"
   gherkai doctor                       # 本机后端：引擎、模型、AWS 身份都应为 ✓
   ngrok config check                   # 隧道：已配置 authtoken
   ```

2. AI agent：Claude Code 或 Codex 已登录并能正常对话。演示中只用它安装 skill 并展示入口，不让它生成用例。

3. 云端后端（可选段用）：部署方已把云端后端部署到与命令行相同的版本，并按 [云端后端演示的准备](./cloud-demo-preparation.md) 注册好 variant `demo`。核对：

   ```bash
   gherkai doctor --backend cloud --prefix vfy- --region us-east-1
   gherkai deploy list-workers --prefix vfy- --region us-east-1
   ```

4. 预热一次，排除首次运行的冷启动，并记下墙钟供现场对照：

   ```bash
   cd ~ && git clone https://github.com/zhiyanliu/gherkai-webapp-demo.git && cd gherkai-webapp-demo
   (cd app && python3 -m http.server 8080 > /tmp/demo-app.log 2>&1 &)
   gherkai run features/level-select.feature --expose-local http://localhost:8080 --region us-east-1
   rm -rf reports && rm -rf ~/gherkai-webapp-demo    # 预热完删掉，演示时重新 clone
   ```

5. 经 ssh 演示跳板机时，本机浏览器要看到被测应用，另开一个端口转发：`ssh -L 8080:localhost:8080 <跳板机>`，然后打开 `http://localhost:8080`。

6. 终端布局：一个终端用于讲解与运行，应用的静态服务放在后台；另开一个浏览器窗口看应用与报告。

## 时间线

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

不执行命令。要点：用例写在 `.feature` 里，一步交给 AI、还是命中项目注册的确定性 step 走代码，由工具按步派发；浏览器在云端；QA 写测试设计，agent 写用例与代码，人验收与决策。

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

讲解：`app/` 是被测应用，`features/` 一个功能域一份，`steps/` 是两个引擎成对的确定性 step；skill 与命令行同版本、每人本机自装、不入库。

### 5:00 三层输入与 agent 的产出

```bash
sed -n 1,40p .claude/skills/gherkai/SKILL.md        # 工具层：skill（Codex 装在 .agents/skills/gherkai/SKILL.md）
cat docs/ui-testing-conventions.md                  # 项目层：约定
cat docs/briefs/level-select.md                     # 任务层：简报
cat features/level-select.feature                   # agent 据简报产出的 feature
```

讲解：放到任何一份简报里都成立的内容不属于简报，归项目约定；工具本身的用法不写进项目约定，交给 skill。仓库里的四份 feature 与全部 step 都是 agent 按简报生成、由人验收后提交的；把简报与 feature 并排看，双引号里的自然语言是 AI 步，`关卡按钮有 "8" 个` 这类是确定性 step。期望只来自需求，看应用只为定位元素。生成的步骤与提示词见文末「自行体验」，演示中不执行。

### 10:00 预检与本机后端运行

```bash
gherkai plan features/*.feature                     # 18 个 job；带「← 确定性」标注的步走代码，其余走 AI
gherkai run features/result.feature --expose-local http://localhost:8080 --region us-east-1
```

运行约 4 分钟。等待期间讲解输出里的三件事：「隧道已建立」一行（本机应用经隧道给云端浏览器访问，凭据每次一换）；`result-replay-and-home` 这个 job 是一条 `@scope` 接续链，三条 scenario 在同一浏览器会话里串行；其余 job 各开一个会话并行。结束后打开报告 `reports/<run_id>/index.html`。

### 14:00 失败诊断与处置

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

讲解四种处置：改断言措辞、落成确定性 step、换引擎、认定应用缺陷并报出。这一例是第四种。

### 19:00 云端后端提交

```bash
gherkai submit features/level-select.feature --backend cloud --prefix vfy- --region us-east-1 \
  --worker-variant demo --expose-local http://localhost:8080
```

命令立刻返回 run_id，记下它。讲解：worker 与浏览器都在云端，本机只持有隧道；云端运行的确定性 step 来自 variant `demo` 的镜像，不是本机的 `steps/`，镜像的构建与注册见 [云端后端演示的准备](./cloud-demo-preparation.md)。

### 21:00 确定性 step 的代码与验收

```bash
cat steps/level_select.py                           # 注册薄壳：模式、说明、示例
sed -n 1,60p steps/_level_select.py                 # 判定逻辑：带等待、失败消息带现场
gherkai list-deterministic --engine novaact
gherkai list-deterministic --engine midscene
uv sync && uv run playwright install chromium && uv run pytest steps/test_level_select.py -q   # 本地单测，可选
```

讲解：QA 验收 feature 文本与预检结果，不读代码；测试开发 review step 代码，看四件事：两引擎成对、判定带等待与超时、失败消息带现场、判定逻辑与注册分离并有单测。

### 25:00 云端结果

```bash
gherkai status <run_id> --wait --backend cloud --prefix vfy- --region us-east-1
gherkai explain <run_id> --backend cloud --prefix vfy- --region us-east-1
```

讲解：`status --wait` 的退出码就是判定；报告在 S3；`explain` 里隧道地址的凭据显示为 `***`。

### 28:00 收尾

费用与速度：运行输出里每个 job 的 token 数与墙钟；确定性 step 零模型费用、毫秒级。分工：QA 写简报与验收、测试开发维护 `steps/`、部署方维护云端后端。采用路径：先在本机后端接一个功能域，再上云端后端。

## 应急

- 本机运行判否但不是预埋的缺陷：直接用它做 14:00 段的素材，`explain` 后按四种处置讲。
- 隧道建立失败：`ngrok config check`；仍失败则跳过本机运行，改为只讲预检与云端段。
- 云端结果到 25:00 仍未终态：先收尾，`status --wait` 放到最后。
- 一次运行里模型服务偶发 5xx 或 AI 判定抖动属于正常现象，重新运行对应 job：`gherkai run <feature> --scope <scope_id> --expose-local http://localhost:8080 --region us-east-1`。

## 自行体验：让 agent 按简报生成 feature 与 step

演示中不执行本节。读者自己走时，先把仓库里已有的产出移开，否则 agent 会直接看到答案；结束后用 git 还原。以选关页为例，agent 需要 10 到 15 分钟。

```bash
cd ~/gherkai-webapp-demo
git rm -rq features steps                           # 移开已有产出（只在工作区与暂存区，不提交）
gherkai skill install --agent claude-code --pointer yes     # 或 --agent codex
claude                                              # Codex 用 codex
```

进入交互界面后粘贴：

```text
按 docs/briefs/level-select.md 写用例与确定性 step，按 docs/ui-testing-conventions.md 的约束与交付物交付。先别真跑。
```

agent 交付后按项目约定验收，再与仓库里的版本对照：

```bash
cat features/level-select.feature
gherkai plan features/level-select.feature
gherkai list-deterministic --engine novaact
gherkai list-deterministic --engine midscene
git diff HEAD -- features/level-select.feature      # 与已提交版本的差异
git checkout HEAD -- features steps && git clean -fd features steps   # 还原仓库
```

本仓库四份 feature 生成时的用时与两种 agent 的操作差异见 [QA 团队的工作方法](./qa-practice-with-gherkai.md) 第 5 节与第 9 节。

## 演示后

```bash
pkill -f "http.server 8080"                        # 停应用
rm -rf ~/gherkai-webapp-demo                       # 演示目录整个删掉，下次重新 clone
```
