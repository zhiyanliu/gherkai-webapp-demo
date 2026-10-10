# gherkai 测试工作流完整演示

从一条业务要求出发，展示用例与确定性步骤生成、执行计划、本机测试、失败反馈，以及恢复后的双引擎云端复验。可直接观看视频，也可配合 Deck 和 runbook 自己操作或现场演示。

| 使用方式 | 资料 |
|---|---|
| 观看完整演示 | [视频](gherkai-demo.mp4) · [章节](chapters.md) · [字幕](gherkai-demo.srt) |
| 现场讲解 | [Deck（含逐页 notes）](gherkai-demo.pptx) · [讲者手册](speaker-notes.md) |
| 自己复现 | [Demo runbook](../../demo-runbook.md) · [Agent 生成任务](../../demo-generation-prompt.md) |
| 阅读视频讲解 | [视频口播与画面安排](video-script.md) |
| 维护材料 | [制作源、素材包与证据说明](internal/README.md) |

定版 Deck、视频、字幕及素材包的校验值见 [SHA256SUMS](SHA256SUMS)。

Deck 共 13 页，视频约 13 分 20 秒，画面已包含字幕；独立 SRT 供播放器或二次编辑使用。现场 runbook 以约 30 分钟为控场预算，包含执行等待，安装与完整生成在开场前完成。

示例固定到 gherkai 1.4.8。中文主线使用 Midscene，3 个接续场景、22 步；云端复验加入 Nova Act 英文结算场景，合计 2 个任务、4 个场景、33 步。新环境请先按 runbook 完成准备，以本次实际判定为准。

本演示可独立使用。产品定位和方法主张见主项目的[价值与方法资料](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/presentations/value-method/README.md)。
