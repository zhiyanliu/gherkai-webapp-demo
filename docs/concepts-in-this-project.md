# 概念对照：gherkai 的概念在本项目里长什么样

概念本身看 gherkai 的文档，这里不解释；每一行给出权威页和本项目里的实例，读完 gherkai 的 README 再看这一页，就知道自己项目里这些东西在哪。

| 概念 | 权威页 | 本项目里的实例 |
|---|---|---|
| 用例是 Gherkin，一个功能域一份 `.feature` | [编写 .feature](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-features.md) | `features/` 下四份：`home-and-language`（F1、F5）、`level-select`（F2）、`quiz`（F3）、`result`（F4） |
| 导航步：双引号里的地址直接打开，不问 AI | 同上 | 每条 scenario 的第一步 `Given 打开 "http://localhost:8080"` |
| AI 步：自然语言交给引擎，动作与判定都由模型完成 | 同上 | `When "点击开始挑战按钮"`、`Then "被选中的拼音选项呈绿色的答对状态"` |
| 确定性 step：命中项目注册的模式就走代码，不问 AI、不投票 | [编写确定性 step](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-deterministic-steps.md) | `Then 得分为 "1"`、`Then 进度显示 "1 / 10"`、`When 选择当前生字的正确拼音`；代码在 `steps/quiz.py` 与 `steps/quiz.mts` |
| 两个引擎各注册一份，模式语义与说明相同 | 同上「两侧对称地写」 | `steps/quiz.py` 对 `steps/quiz.mts`，`steps/level_select.py` 对 `steps/level_select.mts` |
| 判定逻辑与注册分离、配本地单测 | 同上「组织与单测」 | `steps/_checks.py` 与 `steps/_checks.mts` 是判定逻辑，`steps/test_checks.py` 与 `steps/quiz.test.mts` 是单测 |
| 答案不在页面上时按数据判 | 同上「写得能诊断」 | 正确拼音只在应用闭包里；`steps/_vocabulary.json` 是需求附录 A 题库规格的副本，`选择当前生字的正确拼音` 与「依次答对全部 10 题」都查它；单测反过来核对应用源码与规格一致 |
| 引擎路由：Nova Act 只覆盖英文界面，非英文走 Midscene | [编写 .feature](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-features.md)、根 README 的模型披露表 | 中文场景标 `@engine:midscene`；每份 feature 最后一条是英文界面的镜像场景，标 `@engine:novaact`，从 `http://localhost:8080/?lang=en` 进入 |
| scope：多条 scenario 共享一个浏览器会话时才用 | [编写 .feature](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-features.md) | 本项目每条 scenario 都从主页重新进入、互不相干，所以不标 `@scope`，一条 scenario 一个 job |
| tag 筛选 | [运行测试与查看结果](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/running-and-results.md) | `@smoke` 与 `@regression`；`gherkai run features/quiz.feature --tags smoke` |
| 用例预检：零费用看分组、引擎与每步走 AI 还是确定性 | 同上 | `gherkai plan features/*.feature`，四份 feature 共 20 个 job，命中确定性的步后面有「← 确定性」标注 |
| 本机后端与云端后端 | [部署与维护云端后端](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/cloud-backend.md) | 演示以本机后端为主；云端后端用于演示提交链路 |
| 被测应用在本机：隧道 | [测本机或内网里的被测应用](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/local-app-testing.md) | 应用用 `python3 -m http.server 8080` 起在本机，运行时加 `--expose-local http://localhost:8080`，feature 里的地址不改 |
| 失败证据与解释 | [运行测试与查看结果](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/running-and-results.md) | 运行后 `gherkai explain <run_id>`；确定性步失败只有一行原因，所以这里的 step 把页面地址、选择器、期望与实际都写进消息 |
| 三个角色 | 散见各页；合并表在 [QA 团队的工作方法](./qa-practice-with-gherkai.md) 第 1 节 | QA 写简报与验收，测试开发维护 `steps/`，部署方管云端后端 |
