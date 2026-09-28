# 测试约定

本项目用 gherkai 做 UI 测试。AI agent 与人都按这里的约定写用例与代码。

## 目录

- `features/`：一个功能域一份 `.feature`，文件名用英文小写连字符（`quiz.feature`），与 `docs/briefs/` 里的简报一一对应。
- `steps/`：确定性 step 代码。注册文件按主题命名（`quiz.py`、`quiz.mts`），只做注册；判定逻辑放 `_` 前缀的辅助模块（`_checks.py`、`_checks.mts`）；单测文件 Python 以 `test_` 开头、TypeScript 含 `.test.`。两个引擎成对维护，模式语义、说明、示例同文。
- `reports/`：运行产物，不入库。
- `.claude/skills/gherkai/` 与 `.agents/skills/gherkai/`：gherkai 的 agent skill，每人本机执行 `gherkai skill install --agent all` 安装，与自己装的命令行同版本，不入库。

## 被测应用

- 本机运行：`cd app && python3 -m http.server 8080`，地址 `http://localhost:8080`；英文界面 `http://localhost:8080/?lang=en`。
- feature 里照写这个地址。云端浏览器访问本机应用时由运行者加 `--expose-local http://localhost:8080`，用例不改。
- 界面中文为主；英文界面每个功能域覆盖一条代表性场景。

## 用例写法

- 导航步写 `Given 打开 "http://localhost:8080"`；动作步写用户会怎么说；AI 断言写成页面级陈述。
- 精确检查（数值、计数、精确文本、标题、按题库判答案）写成确定性 step。
- tag：每个功能域标 1 到 2 条 `@smoke`，其余 `@regression`。需要接着上一步页面状态的 scenario 用 `@scope:<功能域>-<用途>`，名字带功能域前缀，不用通名。
- 引擎由界面语言决定，agent 标注并说明。

## 派活与验收：每张简报都默认的约束与交付

测试任务简报（`docs/briefs/`）只写这次要测什么；下面这些对每张简报都成立，agent 从这里读，简报不重复。

约束：

- 先预检（`gherkai plan`），不实际运行；实际运行由人发起。
- 确定性 step 两个引擎都要有；判定逻辑放 `_` 前缀的辅助模块并配本地单测；模式写窄，带引号参数与特征词。
- 不改需求口径：需求含糊处标出来问人，不自行放宽或收紧期望。

交付：

- `features/<功能域>.feature`，文件名与简报同名。
- `steps/` 下新增或修改的文件清单。
- `gherkai plan` 的标注与 job 数；两个引擎各一份 `gherkai list-deterministic --engine <引擎>` 的清单。
- 一段说明：哪些检查为什么走了确定性、哪些走了 AI；引擎怎么选的。

## 运行

- 默认只预检（`gherkai plan`），不实际运行；实际运行由人发起。
- 日常在本机后端运行。云端后端只用于演示提交链路；云端运行用的 `steps/` 由测试开发打进 worker 镜像并推送，改了 steps 要重推，做法见 gherkai 用户指南的云端后端一页。
- 汇报用中文。
