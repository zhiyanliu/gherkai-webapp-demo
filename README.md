# gherkai-webapp-demo · 识字大挑战

演示 [gherkai](https://github.com/zhiyanliu/gherkai) 用的示例项目。这里有两样东西：一个纯静态的被测应用，和围绕它写的 gherkai 用例。仓库的形状就是一个使用 gherkai 的普通项目：`app/` 是被测应用，`features/` 放 `.feature` 用例，`steps/` 放确定性 step 代码。

## 被测应用

二年级语文识字课件：主页、选关（8 组）、生字选拼音答题（每组 10 题）、得分与结算。单页静态实现，无外网依赖，断网可运行。界面中英双语：右上角按钮切换，或用地址参数 `?lang=en` 以英文界面启动。产品需求见 [docs/product-requirements.md](./docs/product-requirements.md)。

```bash
cd app && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080 ；英文界面 http://localhost:8080/?lang=en
```

## 先读什么

- gherkai 是什么、怎么工作：看 [gherkai 的 README](https://github.com/zhiyanliu/gherkai) 与[用户指南](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/README.md)，本仓库不重复讲概念。
- 这些概念在本项目里长什么样：[docs/concepts-in-this-project.md](./docs/concepts-in-this-project.md)，一页对照表。
- QA 团队怎样在有 AI agent 的前提下用它：[docs/qa-practice-with-gherkai.md](./docs/qa-practice-with-gherkai.md)。

## 与 gherkai 一起用

- 需求：[docs/product-requirements.md](./docs/product-requirements.md)
- 测试约定（agent 与人都遵守）：[docs/ui-testing-conventions.md](./docs/ui-testing-conventions.md)
- 测试任务简报模板：[docs/test-brief-template.md](./docs/test-brief-template.md)；本项目各功能域的简报在 [docs/briefs/](./docs/briefs/)
- 用例：`features/` 一个功能域一份；确定性 step 代码在 `steps/`，判定逻辑在 `_` 前缀的辅助模块里，配本地单测

本地单测（不开云端浏览器、不调模型）：

```bash
uv sync && uv run playwright install chromium && uv run pytest       # Python 侧
npm install && npm run test:steps                                    # TypeScript 侧
```

（演示步骤随后补充。）

## 第三方依赖

被测应用的前端依赖 Tailwind 与 anime.js 均为 MIT 许可的第三方库，随仓库带一份本地副本，运行时不访问外网。
