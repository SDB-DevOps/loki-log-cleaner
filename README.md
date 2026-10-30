# Cloud-Native Loki Log Cleaning & Sanitization Pipeline

> 云原生日志智能清洗、脱敏与流水线全景演练平台 (Loki Data Cleaning PoC & Production Architecture)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Kubernetes](https://img.shields.io/badge/kubernetes-v1.36-blue?logo=kubernetes)](https://kubernetes.io/)
[![Loki](https://img.shields.io/badge/Grafana-Loki-orange?logo=grafana)](https://grafana.com/oss/loki/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)](https://fastapi.tiangolo.com/)

---

## 📖 项目背景与解决的痛点

在当前云原生可观测性与 AIOps 建设中，日志数据普遍存在两个“卡脖子”问题：
1. **噪音海量、成本失控**：K8s 集群存活探针（如 `kube-probe`、`GET /healthz`）通常霸占了 40%~60% 的日志存储与网络带宽，导致云存储账单居高不下；
2. **安全合规红线**：内部私网 IPv4 地址、认证 Token 密钥在日志中大量明文打印，严重违背安全等保与 GDPR 审计规范。

本项目提供一套完整的**云原生端到端日志清洗、脱敏与质量门禁解决方案**，包含演练原型微服务、自动化测试验收套件、5 步流水线全景时序可视化 WebUI，以及面向生产环境（Promtail / Vector）的下沉配置。

---

## ⚙️ 核心数据清洗流水线时序 (5 大步骤)

```
[STEP 01: 数据摄取] ──> [STEP 02: 缺陷识别] ──> [STEP 03: 降噪过滤] ──> [STEP 04: 安全合规] ──> [STEP 05: 规范输出]
      📥                      🔍                      🚫                      🛡️                      🏷️
原始日志原生抓取         模式引擎毫秒识别        探针噪音拦截丢弃        私网IP与Token掩码       标准级别提取入库
(含探针/明文IP/Token)   (正则打标与高亮定位)    (节约40%+存储开销)      (泄露率严格0.0%)       (赋能纯净存储与AIOps)
```

1. **STEP 01 原始日志摄取 (Ingestion)**：对接 K8s 容器 stdout 或 Grafana Loki 原生日志流；
2. **STEP 02 缺陷特征探测 (Classification)**：毫秒级多模式扫描，标记 `🔴 探针心跳噪音`、`🟡 私网IP泄露`、`🟣 凭据密钥明文`；
3. **STEP 03 冗余降噪拦截 (Drop Gate)**：无价值存活探针直接阻断不入库，立省 40%+ 存储；
4. **STEP 04 敏感数据脱敏 (Sanitization)**：私网 IP 替换为 `[IP_MASK]`，Token 替换为 `[TOKEN_MASK]`，通过深度安全门禁；
5. **STEP 05 规范输出交付 (Delivery)**：标准化日志级别（INFO/WARN/ERROR），结构化输出给下游 Grafana 与 AIOps 智能根因分析引擎。

---

## 📂 项目资产目录

| 文件名 | 说明 |
| :--- | :--- |
| **`loki_cleaner_demo.py`** | 核心演练 WebUI 与实时清洗微服务（含 5 步流水线图、双屏对比与量化看板） |
| **`test_phase1_poc.py`** | 自动化质量门禁测试套件（5 项全自动断言，覆盖安全反查与分类标记） |
| **`run_phase1_demo.ps1`** | Windows 环境一键拉起本地 port-forward 与演示服务的 PowerShell 脚本 |
| **`PHASE_1_POC_DELIVERY_AND_TEST_GUIDE.md`** | Phase 1 交付报告、5分钟路演答辩剧本与测试用例矩阵表（TC-01 ~ TC-08） |
| **`LOKI_DATA_CLEANING_DEMO_GUIDE.md`** | 清洗实操指南，包含原型路线与 Promtail / Vector 生产下沉路线 |
| **`KUBEFLOW_DATA_CLEANING_RESEARCH_REPORT.md`** | 深度调研报告（Vector vs Promtail 选型、数据血缘与架构分析） |
| **`PREDICTIVE_ALGORITHMS_AND_VALIDATION_GUIDE.md`** | Phase 3 算法规划指南（Drain3 模板提取与时序异常预测） |
| **`kubeflow_data_cleaning_architecture.drawio`** | 完整数据架构与流程图源文件（支持 draw.io 直接打开编辑） |

---

## 🚀 快速上手 (本地运行)

### 1. 前置准备
需安装 Python 3.9+ 及依赖：
```bash
pip install fastapi uvicorn requests
```

### 2. 直连集群 Loki 并启动 Demo
```powershell
# 1. 建立与 Loki 端口转发（如果从外部开发机运行）
kubectl port-forward -n monitoring svc/loki 3100:3100

# 2. 启动演示服务
python loki_cleaner_demo.py
```
打开浏览器访问：**`http://localhost:8088`** 即可体验。

### 3. 执行自动化测试门禁
```bash
python test_phase1_poc.py
```
全套 5 项测试（包含 0 泄露 PII 深度反查门禁）将自动执行并给出验收报告。

---

## ☸️ Kubernetes 集群直接部署 (NodePort)

项目支持以 ConfigMap 挂载方式零构建直接在 K8s 运行：
- **命名空间**：`monitoring`
- **内部通信**：自动对接 `http://loki.monitoring.svc:3100`
- **外部访问**：NodePort 暴露（端口 `30888`），团队可通过 `http://<Node-IP>:30888` 实时查看。

---

## 📄 开源许可证
本项目遵循 [MIT License](LICENSE)。
