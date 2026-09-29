#!/usr/bin/env bash
# 把本项目的确定性 step 构建成两个引擎的 worker 定制镜像，并注册为云端后端的一个 variant。
# 可重复执行：同一版本、同一 variant 名重复执行只是重新构建并替换镜像摘要，正在运行的 run 不受影响。
#
# 用法：deploy/push-worker-variant.sh [--variant 名] [--prefix P] [--region R] [--set-default]
#   --variant     variant 名，默认 demo
#   --prefix      云端后端的资源名前缀，默认 vfy-
#   --region      AWS region，默认 us-east-1
#   --set-default 同时把默认指针指向这个 variant（提交时不给 --worker-variant 就用它）
# 前置：本机能执行 docker、gherkai 命令行带 deploy-aws 扩展、AWS 凭证可用，且云端后端已部署为与命令行相同的版本。
set -euo pipefail
cd "$(dirname "$0")/.."

VARIANT=demo; PREFIX=vfy-; REGION=us-east-1; SET_DEFAULT=()
while [ $# -gt 0 ]; do
  case "$1" in
    --variant) VARIANT="$2"; shift 2;;
    --prefix) PREFIX="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    --set-default) SET_DEFAULT=(--set-default); shift;;
    *) echo "未知参数：$1" >&2; exit 2;;
  esac
done

VERSION="$(gherkai --version | awk '{print $2}')"
echo "== 命令行版本 ${VERSION}，variant ${VARIANT}，后端前缀 ${PREFIX}，region ${REGION}"

for ENGINE in novaact midscene; do
  IMAGE="gherkai-webapp-demo-${ENGINE}:${VERSION}"
  echo "== 构建 ${IMAGE}"
  docker build --platform linux/amd64 -f "deploy/worker-variant/Dockerfile.${ENGINE}" \
    --build-arg "GHERKAI_VERSION=${VERSION}" -t "${IMAGE}" .
  echo "== 推送并注册 ${ENGINE}/${VARIANT}"
  gherkai deploy push-worker "${IMAGE}" --engine "${ENGINE}" --variant "${VARIANT}" \
    --prefix "${PREFIX}" --region "${REGION}" "${SET_DEFAULT[@]}"
done

echo "== 当前 variant 清单"
gherkai deploy list-workers --prefix "${PREFIX}" --region "${REGION}"
