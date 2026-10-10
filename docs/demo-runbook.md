# 工作方法演示 runbook

以 PPT 为主线，围绕“再玩一次后，回到第 1 题、得分清零”完成三次测试：本机正常、本机缺陷、恢复后的云端验证。第三次运行保留 Midscene 主线，同时加入现有英文结算场景，由 Nova Act 执行。共三次运行、四个浏览器任务，不增加第四次现场运行。现场目标约 30 分钟，包含讲解、切换与执行等待，讨论另计；具体时间需完整彩排确认。

本演示可以独立进行，不要求先看《价值与方法》。gherkai 用业务用例组织测试，让 AI 与确定性步骤（代码）共同执行，并返回结果和证据，供人或 agent 继续验证。叙事按“明确期望 → 形成与审阅用例 → 混合执行 → 失败依据与后续处置 → 云端复验与多引擎执行 → 复现资料”推进；任务可以在后台运行，页面顺序保持这条因果关系。

相关材料：[Deck、视频与讲稿](presentations/demo/README.md)、[产品需求](product-requirements.md)、[测试简报](briefs/result.md)、[业务用例](../features/result.feature)、[实测证据与素材说明](presentations/demo/internal/README.md)。

执行机按普通使用者的环境准备：安装发行版 gherkai 和 worker，取得示例仓库，然后在示例仓库中按本 runbook 操作。EC2 在这里充当使用者自己的执行机；gherkai 源码仓库用于参考，不是运行演示的前置条件。默认复用仓库已有的 feature 与确定性步骤，交代其来源并审阅关键实现，耗时的生成过程可以跳过；如展示 Agent 生成片段，须使用真实记录并明确为预录。

## 开场前准备

安装、部署、录制及环境排障均在开场前完成。现场不从 clone、安装或生成整套测试代码开始。

第一次复现先完成下面的准备流程，再进入 D1–D8。安装与生成不计入现场 30 分钟预算；自助视频保留安装、生成、审阅与检查的关键实操，剪短下载和生成等待。已有环境先核对版本与状态，避免重复安装或覆盖现场。

### 从新环境开始

本轮实录使用 **gherkai 1.4.8**。以下固定 CLI 与两个 worker 到同一版本，便于复现；接入团队已有后端时，以部署方确认的兼容版本为准。安装发行版即可，无需克隆 gherkai 源码。

1. 准备 Python 3.13 或更新版本、Node.js 22.18 或更新版本、uv、Git，以及已登录的编程 Agent。Node 22.18 起可直接运行本项目 `.mts` 本地单测。运行 `python3 --version`、`node --version`、`uv --version`、`git --version` 核对。操作系统安装方法见 [uv 安装说明](https://docs.astral.sh/uv/getting-started/installation/) 和 [Node.js 下载](https://nodejs.org/en/download)。Agent 的模型访问使用自己的账号或组织配置，与 gherkai 的执行引擎凭证分开。
2. 安装 CLI 与本机 worker：

   ```bash
   uv tool install --python 3.13 'gherkai[local]==1.4.8'
   npm install --global @gherkai/worker-midscene@1.4.8
   gherkai --version
   gherkai list-engines
   ```

   确认 `gherkai`、`gherkai-worker-novaact` 和 `gherkai-worker-midscene` 都能从当前 shell 找到。uv 安装后若提示工具目录不在 PATH，按其提示执行 `uv tool update-shell`，重新打开终端。
3. 在新目录取得演示项目，并安装与 CLI 匹配的 skill：

   ```bash
   git clone https://github.com/zhiyanliu/gherkai-webapp-demo.git
   cd gherkai-webapp-demo
   gherkai skill install --agent all --pointer no
   gherkai doctor
   ```

   skill 安装在项目的 `.agents/skills/gherkai/` 与 `.claude/skills/gherkai/`。项目已有 `AGENTS.md` / `CLAUDE.md` 入口，因此不再追加指针。`doctor` 检查本机工具、worker 与确定性代码能否加载；此时尚未验证 AWS 服务访问或隧道。
4. 由账号或基础设施负责人提供 **执行权限与环境参数**。本例需要目标 region 中的 AgentCore Browser，以及所选引擎使用的 Bedrock / Nova Act 服务；云端段还需要已部署的 gherkai 后端、prefix 和包含本项目代码的双引擎 variant。实例可使用实例角色；工作站可使用组织配置的 AWS profile。不要把密钥写入仓库。完整权限与部署方准备见 [1.4.8 开始使用](https://github.com/zhiyanliu/gherkai/blob/v1.4.8/docs/user-guide/getting-started.md) 和 [云端后端](https://github.com/zhiyanliu/gherkai/blob/v1.4.8/docs/user-guide/cloud-backend.md)。本 runbook 使用已交付的后端，不要求演示者部署基础设施。
5. 安装 [ngrok](https://ngrok.com/download)，在本机配置自己的 authtoken：

   ```bash
   ngrok version
   ngrok config add-authtoken <你的-authtoken>
   ```

   token 从 ngrok 控制台的 **Your Authtoken** 获取；不要录制、分享真实值。`doctor` 不检查 ngrok 的安装与 token 配置。实际运行通过 `--expose-local http://localhost:8080` 暂时向云端浏览器开放测试应用；应用所在机器需持续开机联网。
6. 在单独终端启动应用，并在浏览器检查中文与英文入口。若 8080 已有本应用服务，直接复用：

   ```bash
   cd app
   python3 -m http.server 8080
   ```

   打开 `http://localhost:8080` 和 `http://localhost:8080/?lang=en`。后面的 gherkai 命令回到项目根目录执行。

完成后继续下面的环境参数与预检。只做用例生成、`plan` 与确定性清单检查不需要创建 AWS 浏览器会话；实际 `run` / `submit` 会使用云端服务并产生费用。

### 用现成用例复现，或亲自从需求生成

**直接复现整条 demo**：使用仓库已有 `features/result.feature` 和 `steps/`，从下一节继续。它们是后续正常、缺陷和云端运行的固定输入。

**体验 Agent 生成**：另开一个全新的练习 clone，保留已有基础检查与题库能力，只移除结算页这一域的已有产出。以下删除命令只能在刚创建的 `gherkai-result-practice` 中执行：

```bash
git clone https://github.com/zhiyanliu/gherkai-webapp-demo.git gherkai-result-practice
cd gherkai-result-practice
rm features/result.feature \
  steps/result.py steps/result.mts steps/_result.py steps/_result.mts \
  steps/test_result.py steps/result.test.mts
gherkai skill install --agent all --pointer no
```

若要让 Agent 同时运行确定性实现的本地单测，在这个练习 clone 中先安装开发依赖和本地 Chromium：

```bash
uv sync --python 3.13
npm install --no-save --no-audit --fund=false \
  @gherkai/worker-midscene@1.4.8 playwright@1.56.0
uv run playwright install chromium
./node_modules/.bin/playwright install chromium
```

这些依赖供本地单测使用，实际 gherkai worker 使用自身安装的依赖。Python 与 TypeScript 的 Playwright 版本可能不同，因此分别检查各自需要的浏览器。Python 单测从 `uv run pytest` 进入项目环境；直接使用系统 `python3 -m pytest` 可能找不到刚安装的 pytest。Agent 若采用无人值守方式，事先允许本练习目录内的文件编辑、`gherkai plan`、`gherkai list-deterministic`、`uv run pytest` 和 `node --test`；不要关闭全局权限检查，也不需给它云端部署权限。

在此练习目录启动编程 Agent，发送 [可复制的生成任务](demo-generation-prompt.md)。任务要求读取产品需求、测试简报和项目约定，检查已有确定性能力，生成 feature 与双引擎实现，再执行本地检查。已有的得分、进度、按钮检查与题库作答能力是复用输入，不应说成本次从零生成。

生成结束后核对：

- 需求期望是否一致，六类场景是否覆盖；重玩和返回主页是否保留完整前置与同一 scope。
- 精确检查和重复答题是否命中代码；Python 与 TypeScript 两侧注册是否对应，失败说明是否包含期望、实际与位置。
- 本地单测是否真实通过；两个引擎的清单与 `plan` 是否有加载错误、匹配冲突或意外退回 AI。

```bash
uv run pytest steps/test_result.py
node --test steps/result.test.mts
gherkai list-deterministic --engine midscene
gherkai list-deterministic --engine novaact
gherkai plan features/result.feature
```

Agent 的生成结果可能与仓库版本不同。先审阅差异，再决定采用哪些修改；生成成功和 `plan` 成功都不等于业务通过。若采用自己的产出继续运行，应以自己的 scope、实际步数和判定为准，不套用下文固定的 22 步统计。若要逐项复现视频，返回原演示 clone，使用仓库已审阅的固定输入。改过的确定性代码用于云端前，还需要由发布方更新对应的 worker variant。

### 项目与环境

1. 使用已有演示项目，保留工作区中别人的修改。更新前先检查状态，不删除目录重建。
2. 安装匹配版本的 gherkai CLI、Midscene 与 Nova Act worker、gherkai skill。云端 Midscene 与 Nova Act 的 variant 都应包含本项目各自的确定性步骤，版本与演示 CLI 兼容；由测试开发、基础设施团队提前准备。已有双引擎实测通过的记录；下次演示仍需核对环境，不能把本机预检视为镜像已就绪。
3. 被测应用已在 `http://localhost:8080` 提供服务。已有服务可用就复用，不停止其他人的进程。报告可从既有的 8081 服务查看。
4. 执行机能使用 AWS 浏览器、模型及已有云端后端，ngrok 已配置。应用所在机器持续开机联网，直到使用隧道的测试结束。
5. 准备 PPT、应用、需求与简报、用例与确定性步骤、执行终端、报告六个窗口。报告链接以每次运行实际返回的地址为准。后续命令使用同一个已设置变量的执行终端；讲解时切到 PPT，不必重开 shell。

本例的“本机”指 worker 在执行机上运行，浏览器与模型仍使用 AWS 服务，不是离线模式。云端示例使用 `us-east-1`、前缀 `vfy-`、variant `demo`，其他环境需替换为已确认的值。现场不部署、销毁或修改基础设施。

### 一次性预检

在项目根目录使用 Bash 或 Zsh。下列变量仅用于本次演示，不包含凭证。

```bash
export DEMO_FEATURE=features/result.feature
export DEMO_SCOPE=result-replay-and-home
export DEMO_NOVA_SCENARIO=英文界面下全部答对
export DEMO_ORIGIN=http://localhost:8080
export DEMO_REGION=us-east-1
export DEMO_PREFIX=vfy-
export DEMO_VARIANT=demo
export DEMO_SESSION_DIR="$(mktemp -d /tmp/gherkai-demo.XXXXXX)"

gherkai --version
gherkai doctor
gherkai doctor --backend cloud --prefix "$DEMO_PREFIX" --region "$DEMO_REGION"
gherkai plan "$DEMO_FEATURE" --scope "$DEMO_SCOPE"
```

预检应选中三个接续场景，组成一个 job，使用同一个浏览器会话。当前用例有 22 步：14 个确定性步骤、7 个 AI 步骤、1 个打开网页步骤。若提示派发标注降级，先修复 worker 安装或发现路径，不能把缺失标注解释成全部使用 AI。

三个主线场景存在状态依赖，不能只筛选中间的“再玩一次”场景。正常与缺陷运行均选择完整主线；第三次云端运行选择主线加英文场景。`plan` 不启动浏览器，不证明用例已通过；它按本地注册表标注，云端的确定性代码来自已发布的 variant。

### 双引擎云端范围

复用现有 `features/result.feature` 中的英文场景，不修改用例期望、不临时切换主线引擎。用预检返回的 ID 选择英文任务，避免手写可能随行号变化的 scope：

```bash
gherkai plan "$DEMO_FEATURE" --scenario "$DEMO_NOVA_SCENARIO" --json \
  > "$DEMO_SESSION_DIR/nova-plan.json"
DEMO_NOVA_SCOPE=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["job_count"] == 1 and d["jobs"][0]["engine"] == "novaact"; print(d["jobs"][0]["scope_id"])' \
  "$DEMO_SESSION_DIR/nova-plan.json")

gherkai plan "$DEMO_FEATURE" --scope "$DEMO_SCOPE" --scope "$DEMO_NOVA_SCOPE"
gherkai list-deterministic --engine midscene
gherkai list-deterministic --engine novaact
```

组合预检应为 **2 个 job、4 个场景、33 步**。主线仍是 22 步，英文场景 11 步（7 个确定性步骤、3 个 AI 步骤、1 个导航步骤）。它们独立打开浏览器，归属同一个 run ID。两侧注册清单应包含本项目代码；云端各自镜像内的代码也要另行核对。

新增英文任务意味着多一个浏览器会话，会增加执行费用。一次提交不等于只产生一次会话费用。两个任务可能并发，实际受后端并发配置约束；以本次运行的实际耗时为准。

本次展示的是按场景选择引擎，并共用提交、查询、读取反馈的流程。中文重玩与英文结算覆盖范围不同，不将它们当作同条件性能对比，也不声称原用例、步骤代码无需适配即可互换引擎。显式 `@engine` 标签不会被 `--default-engine` 覆盖。

### 备用材料

- 提前打开正常、缺陷、恢复与云端的实测报告或精选证据，确认可离线展示。
- [素材包](presentations/demo/internal/media.zip) 的 `capture/recording/` 保留定版视频对应的 22 步主线、双引擎结果、报告与截图。包内 `reference/evidence.zip` 是 Deck 部分页码使用的早期 21 步快照；两者区别见[证据说明](presentations/demo/internal/README.md)。不要将归档结果说成本次现场刚刚跑出的结果。
- Agent 的“需求到产出物”和“失败反馈到下一轮验证”均已有真实记录，并纳入完整视频。现场可选播生成片段，或直接审阅已有文件；反馈处理可使用已录下的输入、工具调用、回复和 plan 选段。完整来源、原始耗时与视频段落见内部制作记录，不把讲者分析冒充 agent 输出。
- 完整彩排前检查故障注入与恢复、云端 variant、报告访问和录制材料。30 分钟是控场预算，下次现场演示仍需检查环境并计时彩排。

## 30 分钟控场

| 时间预算 | 段落 | PPT 页 | 操作与观察 |
|---|---|---|---|
| 0–3 分 | D1 业务与路线 | 1–2 | 看应用与需求，明确验收要求和完整路线 |
| 3–6 分 | D2 用例与实现审阅 | 3–4 | 对照需求审阅已有用例与代码；E5 生成片段可选 |
| 6–10:30 | D3 预检与执行分工 | 5–6 | 约 7:00 发起本机正常运行，等待时展示实际得分检查代码 |
| 10:30–12 分 | D4 正常结果 | 7 | 读取本次判定与轨迹，逐项对照验收要求 |
| 12–17 分 | D5 缺陷与依据 | 8 | 注入缺陷，同范围运行，读失败值与现场 |
| 17–20 分 | D6 反馈与处置 | 9 | E7：Agent 消费失败反馈；片段后由演示者恢复应用 |
| 20–28 分 | D7 云端与多引擎 | 10–12 | 提交主线与英文两个任务；分别查看引擎、判定和证据 |
| 28–30 分 | D8 复现资料 | 13 | 演示结束，打开项目与 runbook 入口 |

时间是控场预算，不需要为占满时段而停留。任务提前完成就进入下一段，余量留给切换或延迟。上一轮未结束时不能修改被测应用；超出预算可用已标识的历史材料解释，必要时将后续测试留到演示后，并明确未实时展示的部分。

### D1 · 业务与路线：0–3 分

PPT 第 1–2 页。画面顺序：PPT 提出问题 → 应用与需求 → PPT 确认验收要求及路线。

> 这是一个识字挑战应用。用户完成一组题后，可以再玩一次。新一轮必须回到第一题、得分清零，之后再次完成挑战，还应能返回主页。

用 60–90 秒建立这个参照，再说明三次测试均围绕相同验收要求。环境、skill 已准备，用例与代码复用仓库已有材料；反馈处理使用实际工作录制，现场测试由讲者发起。若采用可选生成片段，先说明其来源。不在开场展开部署、内部错误类型或所有业务分支。

### D2 · 用例与实现审阅：3–6 分

PPT 第 3 页。先打开需求与 `docs/briefs/result.md`，说明产品需求给出验收依据，brief 界定本次测试范围。默认直接打开仓库已提供的 feature 与确定性步骤，说明这些材料可以由 Agent + gherkai skill 按项目约定编写，本次复用并审阅它们，跳过完整生成等待。需要展示生成过程时，可在此播放 E5 约一分钟的真实片段。随后用 `gherkai plan` 查看执行计划与步骤分工；plan 只检查安排，不执行测试。

若采用 E5，录制保留真实输入输出、原始耗时与剪辑标识。先说明项目已有的确定性能力，再展示本次 Agent 实际新增或修改的用例、代码；复用的辅助函数不说成本次从零生成。区分编程 agent 与执行 AI 步骤的引擎。录制产出经 QA 审阅后，必须与后续实测输入对应；审阅中有调整就保留这次调整，不能用一份生成记录配另一份未交代的执行代码。

完成现有材料审阅或可选生成片段后，切第 4 页及实际 `features/result.feature`，先把完整前置展示出来：第一个场景从首页进入第一组，按题库答对 10 题，真实到达 10 分结算页；第二个场景接着重玩；第三个场景再次答题后返回主页。三个 scenario 配置相同的 scope，gherkai 将它们编为一个任务，按书写顺序共用浏览器会话；后续 scenario 接着已有页面状态执行。在 PPT 上沿向下的箭头展开第二个场景。QA 审阅的是用例设计及需求口径，浏览器状态由 gherkai 接续，本例 Given 匹配确定性步骤并检查已有得分，校验重玩测试的前置条件。此处不称“门禁”：普通断言 failed 不自动阻止后续步骤，执行 error 才跳过本场景后续步骤。随后对照重玩节选审阅：

1. 预期结果是否忠于需求：再玩一次后，得分必须为 0。
2. 前置是否明确：点击前已进入最终得分为 10 的结算页。
3. 判定是否可核对：进度 1 / 10、得分 0。

生成文件不等于测试通过。本例 Given 对应得分检查，核对已有状态，不会自动答题或跳转到结算页。这里完成审阅，下一段通过预检核对完整前置是否确实选入执行范围。跳过 E5 时明确本段使用仓库现成材料，不宣称现场生成了这些文件；这不影响后续完整执行与反馈流程。

### D3 · 预检与执行分工：6–10:30

PPT 第 5 页。执行：

```bash
gherkai plan "$DEMO_FEATURE" --scope "$DEMO_SCOPE"
```

对照第 5 页逐项核对终端输出：①选择完整的三个主线场景；②一个 job，共享浏览器状态并按顺序运行；③引擎为 Midscene；④三个场景合计 22 步，逐步标注代码、AI 或导航。下方 14 / 7 / 1 是第四行执行方式的数量分解。上一页解释了前置如何建立，此处只核对执行安排。不能只选中间场景，也不能把预检当作运行结果。

约第 7 分钟发起第一次运行：

```bash
gherkai run "$DEMO_FEATURE" --scope "$DEMO_SCOPE" \
  --backend local --expose-local "$DEMO_ORIGIN" --region "$DEMO_REGION" \
  --json > "$DEMO_SESSION_DIR/normal.json"
```

保持这个执行终端，讲者切到 PPT 第 6 页，打开这一项实际代码：

1. `features/result.feature` 中的 `And 得分为 "0"`。
2. `steps/quiz.mts` 中对应的 `deterministic` 注册，把期望值传给 `scoreIs`。
3. `steps/_checks.mts` 中的 `scoreIs` 与 `expectText`：先确认答题页，等待页面文字符合期望；超时后返回应有值、实际值、页面地址与元素位置，既给出判定，也形成排查依据。

展开 `expectText` 的失败消息拼接，说明 gherkai skill 要求 Agent 编写可诊断的失败说明。确定性步骤本身不产生截图或模型思考，页面现场要从本次运行中相应的 AI 步骤证据读取。此页聚焦实际检查与反馈实现。后续在同次报告中打开 AI 点击轨迹与得分判定，说明两部分怎样共同完成本次用例。答题复用代码的细节需要时再看 `steps/result.mts`，不把该文件当作得分检查的注册位置。

### D4 · 正常结果：10:30–12 分

PPT 第 7 页。运行结束后，在同一终端读取本次 run ID：

```bash
DEMO_NORMAL_RUN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' \
  "$DEMO_SESSION_DIR/normal.json")
```

```bash
gherkai explain "$DEMO_NORMAL_RUN" "$DEMO_SCOPE"
gherkai explain "$DEMO_NORMAL_RUN" "$DEMO_SCOPE" \
  --scenario "再玩一次回到第 1 题且得分清零" --step 1
```

从 PPT 切到本次报告和 AI 点击轨迹，核对进度 1 / 10、得分 0 以及后续返回主页结果，再回到 PPT 总结。若未结束，显示真实状态并切换已标明的归档证据，不宣称本次已通过。

下一段修改应用前，必须确认正常运行已经结束。不重复启动相同任务，也不在正常测试仍执行时注入缺陷。

### D5 · 缺陷与依据：12–17 分

视频保留录制时的脚本路径；归档后注入与恢复工具统一位于 `tools/demo/fault.py`，请使用以下命令。

PPT 第 8 页。说明由演示者故意保留旧得分，按原用例执行第二次测试：

```bash
python3 tools/demo/fault.py inject \
  --state-dir "$DEMO_SESSION_DIR/fault"

gherkai run "$DEMO_FEATURE" --scope "$DEMO_SCOPE" \
  --backend local --expose-local "$DEMO_ORIGIN" --region "$DEMO_REGION" \
  --json > "$DEMO_SESSION_DIR/fault.json"
```

测试失败是预期结果，不要用 `set -e` 或 `&&` 将结果收集、恢复操作绑定到成功退出。等待时说明读取反馈的顺序：任务是否完成 → 失败业务步骤 → 应有值与实际值 → 页面现场。

完成后：

```bash
DEMO_FAULT_RUN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' \
  "$DEMO_SESSION_DIR/fault.json")
gherkai explain "$DEMO_FAULT_RUN" "$DEMO_SCOPE"
gherkai explain "$DEMO_FAULT_RUN" "$DEMO_SCOPE" \
  --scenario "再玩一次回到第 1 题且得分清零" --step 3 --json \
  > "$DEMO_SESSION_DIR/failure-step.json"

gherkai explain "$DEMO_FAULT_RUN" "$DEMO_SCOPE" \
  --scenario "再玩一次回到第 1 题且得分清零" --step 1

gherkai explain "$DEMO_FAULT_RUN" "$DEMO_SCOPE" --json \
  > "$DEMO_SESSION_DIR/failure-feedback.json"
```

先展示 `explain` 的人读输出，再展示同一次失败的 `--json`。`failure-step.json` 聚焦得分检查的期望与实际，该确定性步骤本身没有页面证据引用；随后点名点击步骤，打开同次运行的 AI 轨迹及可用截图。`failure-feedback.json` 保存完整主线，包含前置场景、相关 AI 步骤和失败检查，供下一段按需读取。JSON 不内嵌截图文件，录制时还须确认引用指向的文件可读，并随原始运行资料一同保留。

应观察到点击再玩一次通过、进度回到 1 / 10，但得分应为 0、实际为 10。它是确定性检查失败，不通过增加 AI 断言投票解决。归档截图与本次输出要区分，不能把已知注入位置当成 agent 已推断出的根因。

此段先完成现象与证据核对，紧接下一页看反馈怎样进入后续工作，再恢复应用。

### D6 · 反馈与处置：17–20 分

PPT 第 9 页。播放 E7 约两分钟的真实录制，观察 agent 如何从原要求、失败运行及 gherkai 反馈中核对现象、提出实际判断并选择带前置场景的复验范围。

- 录制时不提前透露故障注入位置，不补写 agent 结论。
- 准备独立的反馈工作区，提供原需求、实测用例、确定性步骤、同次运行记录及可读取的证据。不要把含答案的故障脚本、备份、制作方案或注入标记混入输入。现有注入脚本会在应用源码留下说明注释，因此不把这份带标记的源码作为 Agent 自行定位缺陷的证据。
- 片段必须呈现反馈带来的实际判断：Agent 引用了什么依据、怎样判断问题、下一轮为何选择这个范围。只复述“应为 0、实际 10”还不足以展示反馈循环；结论以它的真实输出为准，不要求预设措辞或虚构修复。
- 现场明确片段使用其标注的失败 run，不能冒充刚才现场测试的即时响应。
- 完整 demo 视频应把失败执行与 agent 消费反馈录在同一条可追溯链上，使用同一录制 run 的证据。
- 反馈可帮助调整测试、完善确定性步骤，也能辅助排查应用缺陷；只展示实际发生的处理，不宣称自主修复。

E7 的真实原始记录约 265 秒，使用失败 run `20261010T015058Z-32ff1b`；完整视频中的 Agent 输入、读取反馈、判断与 plan 已按实际记录选段。现场使用这些预录材料时说明来源。Agent 的补测建议仍需 QA 审阅，尤其要核对是否改变后续场景的前置状态，详见实录说明。

片段后，**确认缺陷测试已结束**，由演示者恢复应用：

```bash
python3 tools/demo/fault.py restore \
  --state-dir "$DEMO_SESSION_DIR/fault"
git diff -- app/index.html
```

脚本按字节恢复备份；注入后若又发生修改会拒绝覆盖，此时保留现场人工核对，不强制重置。恢复后的验证由云端承担，不增加第四次现场运行。

### D7 · 云端复验与多引擎：20–28 分

PPT 第 10 页。确认应用恢复、上一轮终止，先交代本机和云端使用的执行代码来自哪里，再尽早提交，目标约 21:00 前完成：

```bash
gherkai plan "$DEMO_FEATURE" --scope "$DEMO_SCOPE" --scope "$DEMO_NOVA_SCOPE"

DEMO_CLOUD_RUN=$(gherkai submit "$DEMO_FEATURE" \
  --scope "$DEMO_SCOPE" --scope "$DEMO_NOVA_SCOPE" \
  --backend cloud --prefix "$DEMO_PREFIX" --region "$DEMO_REGION" \
  --worker-variant "$DEMO_VARIANT" --expose-local "$DEMO_ORIGIN")
printf '%s\n' "$DEMO_CLOUD_RUN"
```

`submit` 的标准输出是 run ID，没有 `--json` 参数。后续查询必须对应此 ID。

云端执行期间回到第 10 页，按两侧流程图解释分工：左侧是个人修改代码、本机执行、读取反馈后继续迭代；右侧由测试开发、基础设施团队统一发布能力，QA、agent 或流水线提交任务并按 run ID 查询结果。沿发布的向下箭头与调用/返回的横箭头讲述。本机从步骤目录加载代码，云端使用预先发布的 variant。variant 是具名的执行代码与环境，不是另一份业务用例，也不自动读取本地最新步骤。

本次应用仍通过执行机上的隧道提供服务，机器需要保持联网。这个时段不再插入前面的 Agent 生成或失败处理片段。

约第 22 分钟转第 11 页。展示组合 plan 中的两个 job，及英文场景的 `@engine:novaact`、英文页面地址与 AI 操作文本。Midscene 使用 TypeScript 确定性代码，Nova Act 使用 Python；两侧已经成对注册，云端实际使用各自预先发布的镜像。

在第 11 页沿同一 run ID 的两条分支，指出两个任务各自的浏览器会话。两个任务不共享浏览器状态。Nova Act 的英文场景检查结算内容，未覆盖重玩清零；该主线继续由 Midscene 复验。这样分别验证服务化编排与多引擎接入，不混成“更换引擎修好了原来的缺陷”。

约第 25 分钟转第 12 页，先短查询，再决定是否等待：

```bash
gherkai status "$DEMO_CLOUD_RUN" \
  --backend cloud --prefix "$DEMO_PREFIX" --region "$DEMO_REGION"

gherkai status "$DEMO_CLOUD_RUN" --wait \
  --backend cloud --prefix "$DEMO_PREFIX" --region "$DEMO_REGION"

gherkai explain "$DEMO_CLOUD_RUN" "$DEMO_SCOPE" \
  --backend cloud --prefix "$DEMO_PREFIX" --region "$DEMO_REGION"

gherkai explain "$DEMO_CLOUD_RUN" "$DEMO_NOVA_SCOPE" \
  --backend cloud --prefix "$DEMO_PREFIX" --region "$DEMO_REGION"
```

从 PPT 切到同一 run ID 下两个任务各自的状态、逐步结果与报告。先核对主线的得分清零，再核对英文任务的结算结果。第 12 页表格只给出已有 Midscene 主线归档，不代表新增 Nova Act 已实测通过。提交成功、查询成功与业务通过是不同事情。

若第 27 分钟仍未终态，展示真实状态，切换已标明的云端实测归档，并在演示后收回本次结果。不得混用 run ID 或把历史通过结果当成本次通过。

### D8 · 复现资料：28–30 分

PPT 第 13 页。简短结束演示，打开演示项目的 runbook、需求、用例与确定性步骤入口。资料帮助接手者复现同一条流程，再换成自己的业务要求。此处不再重讲价值 deck 的方法主张。问答另计，若前面完成得早即可提前收尾。

演示项目：`github.com/zhiyanliu/gherkai-webapp-demo`。gherkai 主项目在各页页眉。[完整演示资料](presentations/demo/README.md)提供视频、Deck、字幕与讲稿。

## 应急与收尾

| 情况 | 处理 |
|---|---|
| 应用或隧道不可达 | 检查执行机服务与公网可达性；本机和云端浏览器都可能受影响，不能默认切云端绕开 |
| 本机改动与云端结果不一致 | 核对已发布 variant，不把本地预检当成云端镜像已更新的证明；现场不部署 |
| 运行超时段 | 展示真实状态，切换带来源标识的历史证据；不重复发起任务，不混用 run ID |
| 恢复脚本拒绝覆盖 | 保留备份与修改，人工核对；不强制 checkout/reset |
| Nova Act / 双引擎尚未验证 | 保留已验证 Midscene 主线，明确本次未演示第二引擎；不以预检代替实际执行。此为应急降级，不视为双引擎 demo 已验收 |
| Agent 录制不足 | 明确展示范围，避免把讲者分析或已有脚本当作 agent 自主行为 |

结束后确认应用恢复，保存本次三个 run ID 与实际判定。只停止自己启动且已确认不再使用的服务，复用的 8080、8081 服务保持运行。只在结果已归档、无需恢复后清理本次临时目录。
