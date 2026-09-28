# 测试约定

本项目用 gherkai 做 UI 测试。AI agent 与人都按这里的约定写用例与代码。

## 目录

- `features/`：一个功能域一份 `.feature`，文件名用英文小写连字符（`quiz.feature`），与 `docs/briefs/` 里的简报一一对应。
- `steps/`：确定性 step 代码。注册文件按主题命名（`quiz.py`、`quiz.mts`），只做注册；判定逻辑放 `_` 前缀的辅助模块（`_checks.py`、`_checks.mts`）；单测文件 Python 以 `test_` 开头、TypeScript 含 `.test.`。两个引擎成对维护，模式语义、说明、示例同文。
- `reports/`：运行产物，不入库。

## 被测应用

- 本机运行：`cd app && python3 -m http.server 8080`，地址 `http://localhost:8080`；英文界面 `http://localhost:8080/?lang=en`。
- feature 里照写这个地址。云端浏览器访问本机应用时由运行者加 `--expose-local http://localhost:8080`，用例不改。
- 界面中文为主；英文界面每个功能域覆盖一条代表性场景。

## 用例写法

- 导航步写 `Given 打开 "http://localhost:8080"`；动作步写用户会怎么说；AI 断言写成页面级陈述。
- 精确检查（数值、计数、精确文本、标题、按题库判答案）写成确定性 step。
- tag：每个功能域标 1 到 2 条 `@smoke`，其余 `@regression`。需要接着上一步页面状态的 scenario 用 `@scope:<功能域>-<用途>`，名字带功能域前缀，不用通名。
- 引擎由界面语言决定，agent 标注并说明。

## 运行

- 默认只预检（`gherkai plan`），不实际运行；实际运行由人发起。
- 汇报用中文。
