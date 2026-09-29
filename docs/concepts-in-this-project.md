# 概念对照

本页把 gherkai 的核心概念与本项目中的实例逐条对应。概念的定义与用法以 gherkai 的文档为准（见「权威页面」列），本页不重复解释。

| 概念 | 权威页面 | 本项目中的实例 |
|---|---|---|
| 用例用 Gherkin 编写，一个功能域一份 `.feature` | [编写 .feature](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-features.md) | `features/` 下四份：`home-and-language`（F1、F5）、`level-select`（F2）、`quiz`（F3）、`result`（F4） |
| 导航步：双引号内的地址由工具直接打开，不经过模型 | 同上 | 每条 scenario 的第一步 `Given 打开 "http://localhost:8080"` |
| AI 步：自然语言交给引擎，动作与判定由模型完成 | 同上 | `When "点击开始挑战按钮"`、`Then "生字卡上显示的是一个汉字"` |
| 确定性 step：命中项目注册的模式时执行代码，不经过模型、不投票 | [编写确定性 step](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-deterministic-steps.md) | `Then 得分为 "1"`、`Then 进度显示 "1 / 10"`、`When 选择当前生字的正确拼音`；代码在 `steps/quiz.py` 与 `steps/quiz.mts` |
| 两个引擎各注册一份，模式语义与说明相同 | 同上「两侧对称地写」 | `steps/quiz.py` 与 `steps/quiz.mts`，`steps/level_select.py` 与 `steps/level_select.mts` |
| 判定逻辑与注册分离，配本地单测 | 同上「组织与单测」 | 判定逻辑在 `steps/_checks.py` 与 `steps/_checks.mts`；单测在 `steps/test_checks.py` 与 `steps/quiz.test.mts` |
| 答案不在页面上时按数据判定 | 同上「写得能诊断」 | 正确拼音只存在于应用的闭包中。`steps/_vocabulary.json` 是需求附录 A 题库规格的副本，「选择当前生字的正确拼音」与「依次答对全部 10 题」两条 step 都查询它；单测核对应用源码与规格一致 |
| 引擎路由：Nova Act 只覆盖英文界面，非英文界面使用 Midscene | [编写 .feature](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-features.md)；[底层模型披露](https://github.com/zhiyanliu/gherkai/blob/HEAD/README.md#判定由谁做出底层模型披露) | 中文场景标 `@engine:midscene`。每份 feature 的最后一条是英文界面的镜像场景，标 `@engine:novaact`，从 `http://localhost:8080/?lang=en` 进入 |
| scope：仅在多条 scenario 需要共享一个浏览器会话时使用 | [编写 .feature](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/writing-features.md) | 结算页的「全部答对」「再玩一次回到第 1 题且得分清零」「从结算页返回主页」三条场景标 `@scope:result-replay-and-home`，在同一个浏览器会话里按书写顺序串行执行，合成一个 job；其余场景都从主页重新进入、互不依赖，不标 `@scope`，一条 scenario 对应一个 job |
| tag 筛选 | [运行测试与查看结果](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/running-and-results.md) | `@smoke` 与 `@regression`；`gherkai run features/quiz.feature --tags smoke` |
| 用例预检：零费用查看分组、引擎与每步的执行路径 | 同上 | `gherkai plan features/*.feature`。四份 feature 共 18 个 job，命中确定性 step 的步带「← 确定性」标注 |
| 本机后端与云端后端 | [部署与维护云端后端](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/cloud-backend.md) | 演示以本机后端为主；云端后端用于演示提交链路 |
| 被测应用在本机：隧道 | [测本机或内网里的被测应用](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/local-app-testing.md) | 应用以 `python3 -m http.server 8080` 在本机启动，运行时加 `--expose-local http://localhost:8080`，feature 中的地址不变 |
| 失败证据与解释 | [运行测试与查看结果](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/running-and-results.md) | 运行后执行 `gherkai explain <run_id>`。确定性 step 失败时只有一行原因，因此本项目的 step 在失败消息中给出页面地址、选择器、期望值与实际值 |
| 角色分工 | 分散在各页；合并表见 [QA 团队的工作方法](./qa-practice-with-gherkai.md) 第 1 节 | QA 编写简报并验收，测试开发维护 `steps/`，部署方维护云端后端 |
