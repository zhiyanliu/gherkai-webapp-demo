# gherkai-webapp-demo · 识字大挑战

演示 [gherkai](https://github.com/zhiyanliu/gherkai) 用的示例项目。这里有两样东西：一个纯静态的被测应用，和围绕它写的 gherkai 用例。仓库的形状就是一个使用 gherkai 的普通项目：`app/` 是被测应用，`features/` 放 `.feature` 用例，`steps/` 放确定性 step 代码。

## 被测应用

二年级语文识字课件：主页、选关（8 组）、生字选拼音答题（每组 10 题）、得分与结算。单页静态实现，无外网依赖，断网可运行。界面中英双语：右上角按钮切换，或用地址参数 `?lang=en` 以英文界面启动。产品需求见 [docs/product-requirements.md](./docs/product-requirements.md)。

```bash
cd app && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080 ；英文界面 http://localhost:8080/?lang=en
```

## 与 gherkai 一起用

这个仓库按一套 QA 团队的工作方法组织，方法本身写在 [docs/qa-practice-with-gherkai.md](./docs/qa-practice-with-gherkai.md)：QA 备料、按功能域给 AI agent 写测试任务简报、验收产出、运行与修正。

- 需求：[docs/product-requirements.md](./docs/product-requirements.md)
- 测试约定（agent 与人都遵守）：[docs/testing-conventions.md](./docs/testing-conventions.md)
- 测试任务简报模板：[docs/test-brief-template.md](./docs/test-brief-template.md)；本项目各功能域的简报在 [docs/briefs/](./docs/briefs/)
- 用例：`features/` 一个功能域一份；确定性 step 代码在 `steps/`

（用例与演示步骤随后补充。）

## 来源

被测应用取自 [demo-shizi-tiaozhan](https://github.com/zhiyanliu/demo-shizi-tiaozhan) 仓库的课件部分。前端依赖 Tailwind 与 anime.js 均为 MIT 许可的第三方库，随仓库带一份本地副本；图片与音频沿用原仓库资产。
