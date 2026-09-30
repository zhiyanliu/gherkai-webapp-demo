# 云端后端演示的准备

演示 gherkai 云端后端（`--backend cloud`）之前需要完成以下准备；现场使用的命令列在后半部分。所有步骤可重复执行，重复执行得到相同的结果。云端后端的概念、部署与升级见 [部署与维护云端后端](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/cloud-backend.md)。

## 前置条件

- 云端后端已部署，版本与演示机的 gherkai 命令行相同（`gherkai doctor --backend cloud --prefix <前缀> --region <region>` 的 `backend.version` 行显示一致）。部署由部署方完成，不在本页范围内。
- 演示机能执行 `docker`，安装了带部署扩展的命令行（`uv tool install 'gherkai[local,deploy-aws]'`），AWS 凭证可用，且能访问 `ghcr.io`（拉取官方基础镜像）。
- 被测应用在演示机本机运行（`cd app && python3 -m http.server 8080`），演示机安装并配置了 ngrok（见 [测本机或内网里的被测应用](https://github.com/zhiyanliu/gherkai/blob/HEAD/docs/user-guide/local-app-testing.md)）。

## 第一步：把本项目的 step 打进 worker 镜像并注册为 variant

云端 worker 使用的确定性 step 由镜像决定，本机的 `steps/` 目录不会随提交上传。本项目的两份 Dockerfile 在 `deploy/worker-variant/`，各三行：官方基础镜像、复制 `steps/`、设置 `GHERKAI_STEPS_DIR`。

```bash
deploy/push-worker-variant.sh                      # 默认：variant 名 demo，前缀 vfy-，region us-east-1
deploy/push-worker-variant.sh --prefix <前缀> --region <region>   # 其它环境
```

脚本依次构建两个引擎的镜像（`--platform linux/amd64`，版本取自本机 `gherkai --version`）、用 `gherkai deploy push-worker` 推送并注册为 variant `demo`，最后列出当前的 variant 清单。

- 重复执行是安全的：同名 variant 重推只替换镜像摘要并注册新的运行配置，正在运行的 run 仍引用旧镜像层。
- `steps/` 有改动后必须重新执行本步骤，否则云端运行的仍是旧的 step。
- 命令行升级后也要重新执行：variant 按版本隔离，新版本下没有镜像的 variant 不能提交。
- 脚本不改默认指针（部署方初始化为 `base`，即不含任何自定义 step 的官方镜像）。需要让不带 `--worker-variant` 的提交也用本项目的 step 时，加 `--set-default`。

## 第二步：核对

```bash
gherkai deploy list-workers --prefix vfy- --region us-east-1     # 两个引擎下都应有 demo，镜像标签形如 <版本>-demo，版本与 gherkai --version 一致
gherkai doctor --backend cloud --prefix vfy- --region us-east-1  # backend.* 各行为 ✓
gherkai plan features/result.feature                             # 本机预检：确定性标注与 job 数；云端实际用镜像里的 step
```

`plan` 的确定性标注来自本机的 `steps/`，只代表本机视图。第一步完成后两者一致。

## 现场命令

```bash
# 提交：浏览器与 worker 都在云端，本机只持有隧道，提交后命令立即返回 run_id
RUN_ID=$(gherkai submit features/result.feature --backend cloud --prefix vfy- --region us-east-1 \
  --worker-variant demo --expose-local http://localhost:8080)
# 等待判定；到终态时输出报告与判定明细的位置，退出码即判定
gherkai status "$RUN_ID" --wait --backend cloud --prefix vfy- --region us-east-1
# 读失败证据
gherkai explain "$RUN_ID" --backend cloud --prefix vfy- --region us-east-1
```

- `--expose-local` 与 `submit --backend cloud` 组合时，隧道由本机的守护进程持有，演示机在 run 到终态前保持开机联网。
- `status`、`explain` 的 `--backend`、`--prefix`、`--region` 必须与 `submit` 时一致。
- 隧道地址中的凭据在失败消息、`explain` 输出与证据中显示为 `***`；引擎的原生产物与本机的 `run_meta.json` 仍是明文。

## 演示后的清理

- 云端不需要清理：variant 与 revision 由后端按规则回收（退休满 1 小时且无 run 引用），`delete-worker` 尚未提供。
- 本机：`docker image rm gherkai-webapp-demo-novaact:<版本> gherkai-webapp-demo-midscene:<版本>` 可释放磁盘；不删也不影响下次执行。
