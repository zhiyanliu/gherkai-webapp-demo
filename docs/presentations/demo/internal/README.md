# Demo 维护与证据说明

读者入口在[上一级目录](../README.md)，现场操作以 [runbook](../../../demo-runbook.md) 为准。本目录集中保存定版制作源和可恢复素材，不承担运行测试所需的依赖。

## 保留什么

| 资料 | 用途 |
|---|---|
| [可编辑 Deck](../gherkai-demo.pptx) | 页面和内嵌 notes 的维护源；直接编辑此文件 |
| [讲者手册](../speaker-notes.md) | 现场口播、操作、切换和证据来源 |
| [视频讲稿](../video-script.md)、[逐段配置](video-story.json) | 42 个视频片段的口播、画面、观察点与来源映射 |
| [素材包](media.zip)、[逐文件清单](media-manifest.json) | 原始录制、公开 Agent 记录、已采用的 42 段配音及时间戳、13 页 Deck 图片、处理配方与校验结果 |
| [视频合成](video_edit.py)、[画面样式](video_frames.py)、[终端回放](terminal_capture.mjs) | 按保存的输入重建画面、字幕、旁白与整片 |
| [素材恢复](restore_media.py)、[浏览器素材处理](repair_capture.py) | 验证归档，恢复本地制作目录，重建已审阅的浏览器片段 |
| [配音工具](minimax_narration.py) | 只在修改口播时补充配音；原配音已在包内，无需再次调用 API |
| [GitHub 视频记录](github-video.json) | README 内嵌附件地址、原片校验值与播放器设置 |
| [图标与许可证](assets/icons/LICENSE.txt) | 实操与 Deck 共用的 Lucide 图标 |

旧 Deck 生成器、过程方案、样式试验、重复媒体、未采用配音和预览缓存不再维护。定版 PPTX 是页面的可编辑源，素材包内的 PNG 是本次视频实际使用的渲染结果。日后修改 Deck，应同时检查内嵌 notes、讲者手册及相应视频段落。

## 离线恢复与重新制作

素材包中每个文件均有 SHA-256 校验。恢复工具会拒绝覆盖已经修改的素材。以下命令从仓库根目录执行；`work/` 是可再生且不入库的制作目录。

```bash
python3 docs/presentations/demo/internal/restore_media.py --verify-only
python3 docs/presentations/demo/internal/restore_media.py
```

包内结构：

```text
capture/recording/       主线测试、报告、截图、原始 WebM 与 Agent 反馈记录
capture/preparation/     安装、skill 安装、Agent 生成与本地检查的公开记录
capture/repaired/        三段浏览器素材的裁剪与帧映射配方
deck/                   定版 Deck 的 13 张 1920 × 1080 PNG
edit/audio/             实际采用的配音、生成元数据与语音时间戳
edit/narration-manifest.json
terminal-focus/         失败说明的原始终端网格截图及几何信息
reference/              早期 Deck 证据包、当前预检包与定版校验记录
```

视频制作使用 macOS 的 Hiragino Sans GB、Arial、Menlo 字体，以及 Python 的 Pillow 12.3.0、NumPy 2.3.5，Node 的 Playwright 1.62.1、Sharp 0.35.5，FFmpeg 9.0.2（libx264）。这些是本次制作环境的记录，与运行 gherkai 测试的依赖分开。更换字体或编码器后，需重新检查布局和媒体；浏览器重建工具还会核对编码结果的哈希。

`media_paths.py` 默认使用 Codex 本机配套 Node 环境；其他环境可设置 `DEMO_NODE`、`DEMO_NODE_MODULES`、`DEMO_FFMPEG`、`DEMO_FFPROBE`。`DEMO_BUILD_DIR` 可指定独立制作目录。Python 命令需进入已安装 Pillow、NumPy 的环境。

```bash
# 恢复源素材并重建三段浏览器视频；不执行云端测试
python3 docs/presentations/demo/internal/restore_media.py --browser-clips

# 从真实命令、公开事件及文件内容生成终端视图
python3 docs/presentations/demo/internal/video_edit.py prepare
node docs/presentations/demo/internal/terminal_capture.mjs \
  docs/presentations/demo/internal/work/edit/terminal-jobs.json

# 重建画面、时间线、字幕及配音合成
python3 docs/presentations/demo/internal/video_edit.py render
python3 docs/presentations/demo/internal/video_edit.py assemble
python3 docs/presentations/demo/internal/video_edit.py mux
```

输出在 `work/edit/gherkai-demo.mp4`、`gherkai-demo.srt` 与 `chapters.md`，不会自动覆盖定版成品。更新前检查完整视频、字幕断句与词语、画面切换、关键高亮和响度。若只修改 Deck，可从 PPTX 导出等尺寸 PNG 替换 `work/deck/01.png` 至 `13.png`，再审阅受影响的片段。

修改口播时，先改 `video-story.json`，执行 `video_edit.py narration` 更新讲稿与配音清单；`minimax_narration.py` 可按 `--pages` 选择变化片段。API key 从运行时环境或隐藏输入读取，不写入仓库。仅恢复或重建定版视频不需要 key、AWS 权限或模型调用。

### README 内嵌视频

首页使用 GitHub 原生视频附件地址。上传的是同一份已带字幕的定版 MP4，没有另行压缩；GitHub Markdown 渲染出的播放器带 `controls` 和 `muted` 属性，默认静音、由读者点击播放。

更新视频时，通过已登录的 `gh` 调用其官方附件接口，不需要创建 issue，也不在网页编辑器里上传。以下命令只上传附件；将返回的 `url` 独占一行写入根 README 的“完整演示”一节，再更新 `github-video.json`。README 随正常 Git 提交发布。

```bash
DEMO_REPO_ID=$(gh api repos/zhiyanliu/gherkai-webapp-demo --jq .id)
gh api "https://uploads.github.com/user-attachments/assets?name=gherkai-demo.mp4&content_type=video%2Fmp4&repository_id=$DEMO_REPO_ID" \
  --method POST \
  -H 'Content-Type: application/octet-stream' \
  -H 'Accept: application/vnd.github+json' \
  --input docs/presentations/demo/gherkai-demo.mp4
```

参考实现为 GitHub CLI 2.102.0 的 `internal/attachments/client.go`。不要把 Markdown 预览返回的临时签名媒体地址写进 README，使用附件接口返回的稳定地址。

## 主线实测与材料来源

实录日期为 2026-10-10，发行版 CLI 与两个 worker 均为 1.4.8。正常、缺陷和恢复后的云端运行使用同一份仓库审阅版测试输入。

| 记录 | Run ID | 实测结果 |
|---|---|---|
| 本机正常 | `20261010T014303Z-f62da5` | Midscene，3 个接续场景、22 步，通过 |
| 本机缺陷 | `20261010T015058Z-32ff1b` | 相同范围；重玩后得分期望 0、实际 10 |
| 恢复后云端联合提交 | `20261010T021026Z-83bc9b` | Midscene 主线 + Nova Act 英文场景，2 个任务、4 个场景、33 步，通过 |
| 英文场景浏览器录像 | `20261010T021432Z-98918b` | Nova Act，11 步，通过；画面来自独立运行 |

主线分工为 14 个确定性步骤、7 个 AI 步骤、1 次导航。英文任务为 7 个确定性步骤、3 个 AI 步骤、1 次导航，不覆盖重玩清零。两种范围不作性能对比。缺陷由演示者注入和恢复，不能归因于 Agent 自主修复。

原始记录中的输入版本标识为 `b93a1929d703434cf7920942d2f10098b2557e06`，gherkai 1.4 源码参考为 `371a33747165866d4708566b43964ed8bc4f421d`。输入文件及哈希随录制归档，不依赖这些本地制作提交继续存在。正常应用 SHA-256 为 `c42a0dae470ae905777310b9047a268175bd8fad68ed7d0449465d06e08d6e07`。

安装与生成在独立练习目录真实执行。Agent 新增 7 个文件，两个引擎均加载出 22 条确定性注册，本地单测 Python / TypeScript 各 24 项通过；生成稿只做 plan 和本地检查，没有进行 UI 或云端执行。生成耗时约 19 分 29 秒。生成稿主线是 20 步，视频交代了审阅点，再切换到仓库 22 步输入进行后续测试。已有得分检查属于复用代码，不声称它是在这轮生成录制中新写出的。

Agent 反馈片段使用上表的本机失败报告、需求、用例、确定性代码与 skill，未提供应用源码或缺陷注入位置。公开记录约 265 秒：读取失败与页面依据，区分业务表现和待排查根因，随后对完整前置范围实际执行 plan。其补测建议仍需 QA 审阅，恢复复验没有采用这些建议，也没有改变验收要求。

正常段的应用画面来自同次报告截图；缺陷及云端浏览器画面来自真实 Live View 录像。英文录像与联合云端任务是两次运行，联合任务的通过结论来自其自身报告。终端按真实 PTY 命令输出和公开 Agent 事件回放，不是未剪辑桌面录像，不包含隐藏思考。

Deck 第 2、7、8、12 页保留早期已审阅截图与结果，来源为 `reference/evidence.zip` 中 2026-10-01 的 21 步快照。视频相关页面已换用本轮 22 步证据；runbook 的备用材料也以本轮记录为入口。早期截图不能冒充本轮现场结果。

原始 WebM 不改动。制作中的短暂采集缺口按已审阅配方保持前一张真实帧，保留时间与帧映射，不插值、不生成应用画面、不改业务判定；这里只保留原始视频和可恢复配方。此信息仅用于维护与溯源，不加入对外 Deck、视频口播或字幕。

## 定版核对

定版为 13 页 Deck、42 个叙事片段、292 条字幕，视频长 799.72 秒，1920 × 1200、25 fps。页面占 1920 × 1080，底部独立字幕区不遮挡观察点。开头直接显示首页，Deck / 实操之间翻转 0.44 秒，实操内部直接切换，结尾淡出 0.1 秒后保留 0.16 秒黑屏。

旁白采用确认的音色与 `gherkai/格儿凯` 读音、1.1 倍播放；字幕保留完整词语，以阿拉伯数字显示步骤、场景和任务数量。封底为“欢迎试用 gherkai／先复现这条流程，再带入你的业务要求”，口播以“感谢观看”结束。归档只移动和重命名成品，未重新编码，未修改已确认字幕。

素材包的 `reference/video-verification.json` 保存定版媒体哈希及解码、字幕、首尾帧、音画时长与关键高亮的核对结果。观看成品不需要解压素材包。
