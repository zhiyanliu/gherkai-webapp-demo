# gherkai-webapp-demo · 识字大挑战

本仓库是演示 [gherkai](https://github.com/zhiyanliu/gherkai) 的示例项目，包含两部分：一个纯静态的被测应用，以及针对该应用编写的 gherkai 用例。仓库结构与使用 gherkai 的普通项目相同：`app/` 存放被测应用，`features/` 存放 `.feature` 用例，`steps/` 存放确定性 step 代码。

## 被测应用

二年级语文识字课件：主页、选关（8 组）、生字选拼音答题（每组 10 题）、得分与结算。单页静态实现，无外网依赖，断网可运行。界面支持中英双语：通过右上角的按钮切换，或使用地址参数 `?lang=en` 以英文界面启动。产品需求见 [docs/product-requirements.md](./docs/product-requirements.md)。

```bash
cd app && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080 ；英文界面 http://localhost:8080/?lang=en
```

## 仓库内容

仓库中的每一部分属于三类之一：**输入**由产品或 QA 提供；**生成**由 AI agent 按简报产出、经人验收后提交；**维护**由人负责。

```text
gherkai-webapp-demo/
├── app/                              被测应用（纯静态页面）。输入：开发团队提供
├── docs/
│   ├── product-requirements.md       需求文档。输入：产品提供；用例期望的唯一来源
│   ├── ui-testing-conventions.md     测试约定。维护：QA 与测试开发；agent 与人都遵守
│   ├── test-brief-template.md        测试任务简报模板。维护：QA
│   ├── briefs/                       四份简报（每个功能域一份）。输入：QA 的测试设计产物
│   ├── qa-practice-with-gherkai.md   QA 团队的工作方法。维护：QA
│   ├── concepts-in-this-project.md   gherkai 概念与本项目实例的对照。维护：测试开发
│   ├── cloud-demo-preparation.md     云端后端演示的准备。维护：部署方与测试开发
│   └── demo-runbook.md               演示 runbook。维护：演示者
├── features/                         Gherkin 用例，每个功能域一份。生成：agent 按简报产出，QA 验收
├── steps/                            两个引擎的确定性 step 代码、判定逻辑与单测。生成：agent 产出，测试开发 review 并维护
├── deploy/                           worker 定制镜像的 Dockerfile 与构建推送脚本。维护：测试开发与部署方
├── CLAUDE.md、AGENTS.md              两种 agent 的项目入口，指向测试约定与 skill。维护：由 skill 安装命令追加提示行
├── pyproject.toml、uv.lock           Python 侧单测的依赖
├── package.json、package-lock.json   TypeScript 侧单测的依赖
└── .claude/skills/、.agents/skills/  gherkai 的 agent skill。每人本机安装，不入库
```

## 阅读指引

- gherkai 的定位与工作原理：参见 [gherkai 的 README](https://github.com/zhiyanliu/gherkai) 与[用户指南](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/README.md)。本仓库不重复介绍这些概念。
- 上述概念在本项目中的对应内容：[docs/concepts-in-this-project.md](./docs/concepts-in-this-project.md)，以对照表形式列出。
- QA 团队在使用 AI agent 的前提下如何应用 gherkai：[docs/qa-practice-with-gherkai.md](./docs/qa-practice-with-gherkai.md)。

## 配合 gherkai 使用

- 需求：[docs/product-requirements.md](./docs/product-requirements.md)
- 测试约定（AI agent 与测试人员均须遵守）：[docs/ui-testing-conventions.md](./docs/ui-testing-conventions.md)
- 测试任务简报模板：[docs/test-brief-template.md](./docs/test-brief-template.md)；本项目各功能域的简报在 [docs/briefs/](./docs/briefs/)
- 云端后端演示的准备（把本项目的 step 打进 worker 镜像并注册为 variant）：[docs/cloud-demo-preparation.md](./docs/cloud-demo-preparation.md)
- 用例：`features/` 中每个功能域对应一份用例文件；确定性 step 代码位于 `steps/`，判定逻辑位于 `_` 前缀的辅助模块中，并配有本地单元测试

本地单元测试（不启动云端浏览器，不调用模型）：

```bash
uv sync && uv run playwright install chromium && uv run pytest       # Python 侧
npm install && npm run test:steps                                    # TypeScript 侧
```

演示流程（30 分钟时间线）见 [docs/demo-runbook.md](./docs/demo-runbook.md)。

## 许可证

本仓库以 [MIT 许可证](./LICENSE)发布。

## 第三方依赖

被测应用的前端依赖 Tailwind 与 anime.js 均为 MIT 许可的第三方库。仓库内附带这两个库的本地副本，运行时不访问外网。
