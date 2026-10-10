# 从需求生成结算页测试

在准备好的练习项目根目录打开编程 Agent，发送下面的任务。项目里的 `gherkai` skill 应先安装好。执行前按 [runbook](demo-runbook.md) 准备独立练习目录，避免覆盖演示仓库中的已有用例。

```text
请使用 gherkai skill，完成 docs/briefs/result.md 的结算页测试任务。

先阅读 docs/ui-testing-conventions.md、docs/product-requirements.md 和这份简报。
验收期望只来自产品需求；应用源码仅用于定位元素和实现操作。
先检查两个引擎已有的确定性步骤，复用已有的得分、进度、按钮检查和题库作答能力。

产出 features/result.feature，以及 steps/ 下所需的 Python 和 TypeScript 确定性步骤及本地单测。
覆盖简报中的六类场景。全部答对、再玩一次、返回主页要在同一个 scope 中接续真实页面状态；
中文场景使用 Midscene，英文代表场景使用 Nova Act。
精确数值、文案与重复答题使用确定性代码；页面整体语义和适合 AI 的操作交给 AI。
确定性检查要等待页面就绪，失败时返回期望值、实际值、元素位置与页面地址。

只做 plan、两个引擎的 list-deterministic 和本地单测，不执行 gherkai run / submit、不启动隧道。
开发依赖已按 runbook 安装。Python 单测使用 uv run pytest steps/test_result.py，
TypeScript 单测使用 node --test steps/result.test.mts；不要用系统 python3 代替项目的 uv 环境。
完成后说明新增与复用的文件、代码与 AI 的分工、plan 的场景数和 job 数，以及需要 QA 确认的事项。
不要改需求、降低验收条件，或为了得到通过结果而调整期望。
```

生成结束后由 QA 审阅业务要求与场景接续，由测试开发核对确定性实现。`plan` 通过只表示执行安排能够解析，不代表业务测试通过。随后是否运行、选择多大范围，以审阅后的用例和实际计划为准。
