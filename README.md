# gherkai-webapp-demo · 识字大挑战

演示 [gherkai](https://github.com/zhiyanliu/gherkai) 用的示例项目。这里有两样东西：一个纯静态的被测应用，和围绕它写的 gherkai 用例。仓库的形状就是一个使用 gherkai 的普通项目：`app/` 是被测应用，`features/` 放 `.feature` 用例，`steps/` 放确定性 step 代码。

## 被测应用

二年级语文识字课件：主页、选关（8 组）、生字选拼音答题（每组 10 题）、得分与结算。单页静态实现，无外网依赖，断网可运行。

```bash
cd app && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 与 gherkai 一起用

（待补：用例说明与演示步骤）

## 来源

被测应用取自 [demo-shizi-tiaozhan](https://github.com/zhiyanliu/demo-shizi-tiaozhan) 仓库的课件部分。前端依赖 Tailwind 与 anime.js 均为 MIT 许可的第三方库，随仓库带一份本地副本；图片与音频沿用原仓库资产。
