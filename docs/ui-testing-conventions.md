# 测试约定

本项目用 gherkai 做 UI 测试。gherkai 本身的用法（编写用例与确定性 step、预检、诊断）以 gherkai 的 agent skill 与用户指南为准；本文只记录本项目自己的约定，不复述 skill 已有的规则。AI agent 与人都按本文执行。

## 目录与命名

- `features/`：一个功能域一份 `.feature`，文件名为英文小写连字符（如 `quiz.feature`），与 `docs/briefs/` 下的简报同名、一一对应。
- `steps/`：确定性 step 代码。注册文件按功能域命名、与 feature 同名（`quiz.py`、`quiz.mts`）；判定逻辑放 `_` 前缀的辅助模块（`_checks.py`、`_checks.mts`）；单测文件 Python 以 `test_` 开头、TypeScript 含 `.test.`。判定逻辑与注册分离、两个引擎成对、本地单测等写法按 skill 的确定性 step 参考执行。
- `reports/`：运行产物，不入库。
- `.claude/skills/gherkai/` 与 `.agents/skills/gherkai/`：gherkai 的 agent skill。每人在本机执行 `gherkai skill install --agent all` 安装，版本与本机命令行一致，不入库。

## 被测应用与需求

- 应用在本机运行：`cd app && python3 -m http.server 8080`，地址为 `http://localhost:8080`；英文界面为 `http://localhost:8080/?lang=en`。feature 中照写这个地址。云端浏览器访问本机应用所需的 `--expose-local http://localhost:8080` 由运行者在实际运行时给出，用例不改。
- 界面以中文为主。每个功能域另有一条英文界面的代表性场景。
- 需求的唯一来源是 `docs/product-requirements.md`，包括附录中的规格表（题库）。需求缺口的确认对象是 QA。

## 用例约定

- feature 文件头部只保留两行指针：对应的需求条目、对应的简报。引擎选择、分工理由与注意事项写在交付时的汇报中，不写进 feature。
- tag：每个功能域标 1 到 2 条 `@smoke`，其余标 `@regression`。需要接续上一条 scenario 页面状态的用 `@scope:<功能域>-<用途>`；同一接续链上的 scenario 标相同的 tag，整条链按一条 smoke 计，因为 tag 筛选只减少运行的 scenario、不会把前置场景带回来。
- 汇报使用中文。

## 每份简报都默认的约束与交付

测试任务简报（`docs/briefs/`）只写这次要测什么。以下各项对每份简报都成立，agent 从本文读取，简报不重复。

约束：

- 只做预检，不实际运行。允许与禁止执行的命令见「运行」一节。
- 不改变需求口径。需求含糊或缺少规格时标出并向 QA 确认，不自行放宽或收紧期望。

交付：

- `features/<功能域>.feature`，文件名与简报同名。
- `steps/` 下新增或修改的文件清单。
- `gherkai plan` 的标注与 job 数；两个引擎各一份 `gherkai list-deterministic --engine <引擎>` 的清单。
- 一段说明：哪些检查为什么走确定性 step、哪些交给 AI 判定；引擎如何选择；需求缺口（如有）。

## 运行

- agent 不执行 `gherkai run`、`gherkai submit`、`gherkai status --wait`，包括为了验证自己写的用例。实际运行只由人发起。agent 可以执行的命令只有 `gherkai plan`、`gherkai list-deterministic`、`gherkai list-engines`、不带云端参数的 `gherkai doctor`，以及 `steps/` 的本地单测。
- agent 不起隧道。`--expose-local` 是运行时选项，随实际运行由人给出。
- 日常在本机后端运行；云端后端只用于演示提交链路。云端运行使用的 `steps/` 由测试开发打进 worker 镜像并推送，修改 steps 后需要重推，做法见 gherkai 用户指南的云端后端一页。
