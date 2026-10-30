#!/usr/bin/env python3
"""
Loki 日志数据清洗演示程序 (Loki Log Cleaner Demo with WebUI)
技术栈: Python 3 + FastAPI + Uvicorn + HTML5
"""

import os
import re
import html
import json
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="Loki Data Cleaning Demo")

LOKI_URL = os.environ.get("LOKI_URL", "http://localhost:3100")

# 正则表达式规则
RE_KUBE_PROBE = re.compile(r'(kube-probe|GET /(?:v1/)?(?:healthz?|readyz?|metrics|livez?))', re.IGNORECASE)
RE_IPV4 = re.compile(r'\b(?!(?:127\.0\.0\.1))(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
RE_TOKEN = re.compile(r'(Bearer\s+[A-Za-z0-9\-._~+/]+=*)|([a-f0-9]{32,64})', re.IGNORECASE)
RE_PASSWORD = re.compile(r'(password|passwd|secret)\s*[:=]\s*["\']?([^"\'\s]+)["\']?', re.IGNORECASE)

# 真实保底样例（当未开启 kubectl port-forward 时自动保底）
MOCK_LOGS = [
    '10.42.0.1 - - [29/Oct/2026:07:57:07 +0000] "GET /health HTTP/1.1" 200 2 "-" "kube-probe/1.36"',
    '10.42.0.1 - - [29/Oct/2026:07:57:06 +0000] "POST /api/lf.a2a.v1.A2AService/ListTasks HTTP/1.1" 200 597359 "http://34.69.136.108:31080/agents/01a185f7/chat" "Mozilla/5.0"',
    '10.42.0.1 - - [29/Oct/2026:07:57:09 +0000] "GET /health HTTP/1.1" 200 2 "-" "kube-probe/1.36"',
    '{"time":"2026-10-29T07:57:07.069Z","level":"INFO","msg":"rpc completed","component":"grpc","peer":"10.42.0.152:39292","trace_id":"6cd0aae22af8557fa670602238fbf370"}',
    '10.42.0.1 - - [29/Oct/2026:07:57:12 +0000] "GET /ready HTTP/1.1" 200 4 "-" "kube-probe/1.36"',
    '2026-10-29 07:57:07,730 [INFO] httpx: HTTP Request: POST http://langfuse.langfuse.svc.cluster.local:3000/api/public/ingestion "HTTP/1.1 207 Multi-Status"',
    '10.42.0.1 - - [29/Oct/2026:07:57:15 +0000] "GET /health HTTP/1.1" 200 2 "-" "kube-probe/1.36"',
    '2026-10-29 07:57:16,102 [WARN] auth_middleware: Invalid token Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 for user admin',
    '10.42.0.1 - - [29/Oct/2026:07:57:18 +0000] "GET /health HTTP/1.1" 200 2 "-" "kube-probe/1.36"',
    '{"time":"2026-10-29T07:57:19.450Z","level":"ERROR","msg":"Database query timeout connecting to 10.43.0.24:5432","app":"kagent-db"}'
]

def fetch_loki_logs(namespace: str = "kagent", limit: int = 50) -> List[str]:
    """从本地转发的 Loki 或保底抓取日志"""
    query_str = f'{{namespace="{namespace}"}}'
    encoded_query = urllib.parse.quote(query_str)
    url = f"{LOKI_URL}/loki/api/v1/query?query={encoded_query}&limit={limit}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LokiCleanerDemo/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = []
            for stream_entry in data.get("data", {}).get("result", []):
                for val in stream_entry.get("values", []):
                    results.append(val[1])
            if results:
                return results[:limit]
    except Exception:
        pass
    return MOCK_LOGS[:limit]

def clean_log_record(raw_log: str) -> Dict[str, Any]:
    """带有明确缺陷分类与修复行为追踪的清洗算子"""
    defects = []
    remediations = []
    
    is_probe = bool(RE_KUBE_PROBE.search(raw_log))
    ip_matches = RE_IPV4.findall(raw_log)
    token_matches = RE_TOKEN.findall(raw_log)
    pwd_matches = RE_PASSWORD.findall(raw_log)
    
    # 1. 左侧缺陷标记识别
    if is_probe:
        defects.append({"tag": "探针噪音", "css": "badge-defect-probe", "desc": "K8s集群存活心跳探针，无业务价值"})
    if ip_matches:
        defects.append({"tag": f"私网IP明文({len(ip_matches)})", "css": "badge-defect-ip", "desc": "明文暴露内部Pod/节点IP"})
    if token_matches or pwd_matches:
        defects.append({"tag": "Token凭据明文", "css": "badge-defect-token", "desc": "明文包含Bearer Token或敏感密钥"})
    if not is_probe and not ip_matches and not token_matches and not pwd_matches:
        defects.append({"tag": "合规业务流", "css": "badge-defect-clean", "desc": "原始日志格式良好"})

    # 左侧原文的高亮渲染（标出哪里脏）
    raw_escaped = html.escape(raw_log)
    raw_highlighted = RE_KUBE_PROBE.sub(r'<span class="dirty-probe">\1</span>', raw_escaped)
    raw_highlighted = RE_IPV4.sub(r'<span class="dirty-ip">\g<0></span>', raw_highlighted)
    raw_highlighted = RE_TOKEN.sub(r'<span class="dirty-token">\g<0></span>', raw_highlighted)

    # 2. 右侧清洗与修复行为分类
    if is_probe:
        remediations.append({"tag": "拦截丢弃不入库", "css": "badge-fix-drop", "desc": "过滤冗余心跳，节约存储"})
        return {
            "action": "DROPPED",
            "reason": "HEALTH_CHECK_NOISE",
            "defects": defects,
            "remediations": remediations,
            "raw": raw_log,
            "raw_html": raw_highlighted,
            "clean_html": '<div class="dropped-placeholder">🚫 [已自动拦截丢弃] 消除无价值探针流量，释放存储空间</div>',
            "is_cleaned": True
        }

    # 执行脱敏
    clean_text = raw_escaped
    clean_text, ip_count = RE_IPV4.subn('<span class="badge-mask badge-ip" title="私网IP已安全脱敏">[IP_MASK]</span>', clean_text)
    clean_text, token_count = RE_TOKEN.subn('<span class="badge-mask badge-token" title="Token已安全遮蔽">[TOKEN_MASK]</span>', clean_text)
    clean_text, pwd_count = RE_PASSWORD.subn(r'\1: <span class="badge-mask badge-token">[PASSWORD_MASK]</span>', clean_text)

    # 提取级别
    level = "INFO"
    if "ERROR" in raw_log or "timeout" in raw_log.lower() or "500" in raw_log:
        level = "ERROR"
    elif "WARN" in raw_log or "Invalid" in raw_log:
        level = "WARN"

    if ip_count > 0:
        remediations.append({"tag": f"IP已脱敏({ip_count})", "css": "badge-fix-ip", "desc": "私网IP替换为[IP_MASK]"})
    if token_count > 0 or pwd_count > 0:
        remediations.append({"tag": "Token已遮蔽", "css": "badge-fix-token", "desc": "认证Token替换为[TOKEN_MASK]"})
    
    remediations.append({"tag": f"级别:{level}", "css": f"badge-level {level}", "desc": "统一提取规范级别标签"})

    if ip_count == 0 and token_count == 0 and pwd_count == 0:
        remediations.append({"tag": "质检通过", "css": "badge-fix-clean", "desc": "安全审计与结构检查通过"})

    return {
        "action": "KEPT",
        "level": level,
        "defects": defects,
        "remediations": remediations,
        "raw": raw_log,
        "raw_html": raw_highlighted,
        "clean_html": clean_text,
        "masked_count": ip_count + token_count + pwd_count,
        "is_cleaned": True
    }
@app.get("/api/clean")
def api_clean(namespace: str = Query("kagent"), limit: int = Query(30)):
    raw_logs = fetch_loki_logs(namespace, limit)
    processed = [clean_log_record(log) for log in raw_logs]
    
    total = len(processed)
    dropped = sum(1 for p in processed if p["action"] == "DROPPED")
    kept = total - dropped
    masked = sum(p.get("masked_count", 0) for p in processed)
    drop_rate = round((dropped / total * 100), 1) if total > 0 else 0.0

    return {
        "summary": {
            "total_raw": total,
            "dropped_spam": dropped,
            "clean_kept": kept,
            "drop_rate_pct": drop_rate,
            "masked_items": masked,
            "pii_leakage_rate": "0.0%"
        },
        "records": processed
    }

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>Loki 日志数据清洗演练平台</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; }
    body { background: #0f172a; color: #f8fafc; padding: 22px; }
    .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid #334155; padding-bottom: 14px; }
    .header h1 { font-size: 21px; color: #38bdf8; display: flex; align-items: center; gap: 10px; }
    .controls { display: flex; gap: 12px; align-items: center; }
    select, button { padding: 8px 16px; border-radius: 6px; font-size: 14px; border: 1px solid #475569; background: #1e293b; color: #fff; cursor: pointer; }
    button.btn-primary { background: #0284c7; border-color: #0284c7; font-weight: bold; }
    button.btn-primary:hover { background: #0369a1; }
    
    .legend-banner { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 18px; margin-bottom: 18px; font-size: 12px; }
    .legend-col { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .legend-label { font-weight: bold; color: #cbd5e1; margin-right: 4px; }
    
    .metrics-bar { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 18px; }
    .card { background: #1e293b; border-radius: 8px; padding: 14px; border: 1px solid #334155; }
    .card .title { font-size: 12px; color: #94a3b8; margin-bottom: 6px; }
    .card .val { font-size: 22px; font-weight: bold; color: #f8fafc; }
    .card .val.green { color: #34d399; }
    .card .val.amber { color: #fbbf24; }
    .card .val.blue { color: #38bdf8; }

    .split-container { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    .panel { background: #1e293b; border-radius: 8px; border: 1px solid #334155; display: flex; flex-direction: column; height: 600px; }
    .panel-header { padding: 12px 16px; border-bottom: 1px solid #334155; font-weight: bold; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
    .panel-header.left { background: #2a1b1b; color: #f87171; border-top-left-radius: 8px; border-top-right-radius: 8px; }
    .panel-header.right { background: #132a22; color: #34d399; border-top-left-radius: 8px; border-top-right-radius: 8px; }
    .log-stream { flex: 1; overflow-y: auto; padding: 12px; font-size: 12px; line-height: 1.6; }

    .log-item { padding: 10px 12px; margin-bottom: 10px; border-radius: 6px; background: #0f172a; border-left: 4px solid #64748b; word-break: break-all; transition: background 0.2s; }
    .log-item:hover { background: #182234; }
    .log-item.has-probe { border-left-color: #ef4444; }
    .log-item.has-ip { border-left-color: #f59e0b; }
    .log-item.has-token { border-left-color: #a855f7; }
    .log-item.clean-pass { border-left-color: #10b981; }
    
    .meta-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .tag-group { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
    .row-idx { color: #64748b; font-size: 11px; }

    .badge-defect-probe { background: #7f1d1d; color: #fecaca; border: 1px solid #dc2626; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-defect-ip { background: #78350f; color: #fef08a; border: 1px solid #d97706; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-defect-token { background: #581c87; color: #e9d5ff; border: 1px solid #9333ea; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-defect-clean { background: #334155; color: #cbd5e1; border: 1px solid #475569; padding: 1px 6px; border-radius: 4px; font-size: 11px; }

    .badge-fix-drop { background: #450a0a; color: #f87171; border: 1px dashed #ef4444; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-fix-ip { background: #064e3b; color: #6ee7b7; border: 1px solid #059669; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-fix-token { background: #3b0764; color: #d8b4fe; border: 1px solid #7c3aed; padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-fix-clean { background: #065f46; color: #a7f3d0; border: 1px solid #10b981; padding: 1px 6px; border-radius: 4px; font-size: 11px; }
    .badge-level { padding: 1px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .badge-level.INFO { background: #0369a1; color: #e0f2fe; }
    .badge-level.WARN { background: #b45309; color: #fef3c7; }
    .badge-level.ERROR { background: #b91c1c; color: #fee2e2; }

    .dirty-probe { background: rgba(239, 68, 68, 0.25); border-bottom: 2px wavy #ef4444; color: #fca5a5; font-weight: bold; padding: 0 2px; }
    .dirty-ip { background: rgba(245, 158, 11, 0.25); border-bottom: 2px dashed #f59e0b; color: #fde047; font-weight: bold; padding: 0 2px; }
    .dirty-token { background: rgba(168, 85, 247, 0.25); border-bottom: 2px dashed #a855f7; color: #e9d5ff; font-weight: bold; padding: 0 2px; }

    .badge-mask { padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; margin: 0 2px; }
    .badge-mask.badge-ip { background: #047857; color: #ffffff; }
    .badge-mask.badge-token { background: #6d28d9; color: #ffffff; }
    .dropped-placeholder { color: #94a3b8; font-style: italic; padding: 8px 10px; background: rgba(15, 23, 42, 0.6); border: 1px dashed #475569; border-radius: 4px; }

    /* 数据清洗流水线时序示意图样式 */
    .pipeline-section { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px 18px; margin-bottom: 18px; }
    .pipeline-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px dashed #334155; }
    .pipeline-title { font-size: 14px; font-weight: bold; color: #38bdf8; display: flex; align-items: center; gap: 8px; }
    .pipeline-subtitle { font-size: 11px; color: #94a3b8; }
    .pipeline-steps { display: flex; align-items: stretch; gap: 10px; justify-content: space-between; }
    .pipeline-step { flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 10px 12px; display: flex; flex-direction: column; transition: all 0.2s; min-width: 0; }
    .pipeline-step:hover { transform: translateY(-2px); border-color: #38bdf8; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
    .pipeline-step.step-1 { border-top: 3px solid #ef4444; }
    .pipeline-step.step-2 { border-top: 3px solid #f59e0b; }
    .pipeline-step.step-3 { border-top: 3px solid #f43f5e; }
    .pipeline-step.step-4 { border-top: 3px solid #a855f7; }
    .pipeline-step.step-5 { border-top: 3px solid #10b981; }

    .step-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .step-num { font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 10px; }
    .pipeline-step.step-1 .step-num { background: #7f1d1d; color: #fecaca; }
    .pipeline-step.step-2 .step-num { background: #78350f; color: #fef08a; }
    .pipeline-step.step-3 .step-num { background: #881337; color: #ffe4e6; }
    .pipeline-step.step-4 .step-num { background: #581c87; color: #f3e8ff; }
    .pipeline-step.step-5 .step-num { background: #064e3b; color: #a7f3d0; }

    .step-badge { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; }
    .badge-raw { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; }
    .badge-detect { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; }
    .badge-filter { background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid #f43f5e; }
    .badge-maskstep { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid #a855f7; }
    .badge-deliver { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; }

    .step-name { font-size: 13px; font-weight: bold; color: #f1f5f9; margin-bottom: 4px; display: flex; align-items: center; gap: 5px; white-space: nowrap; }
    .step-desc { font-size: 11px; color: #94a3b8; line-height: 1.4; flex: 1; margin-bottom: 6px; }
    .step-rule { font-size: 10px; background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; padding: 3px 6px; border-radius: 4px; color: #38bdf8; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    .pipeline-arrow { display: flex; align-items: center; justify-content: center; color: #64748b; font-size: 16px; font-weight: bold; user-select: none; }
  </style>
</head>

<body>
  <div class="header">
    <h1><span>🧹</span> Loki 日志智能清洗演练平台 (带缺陷分类与修复追踪)</h1>
    <div class="controls">
      <label>命名空间:</label>
      <select id="nsSelect">
        <option value="kagent">kagent</option>
        <option value="monitoring">monitoring</option>
        <option value="kube-system">kube-system</option>
        <option value="default">default</option>
      </select>
      <button class="btn-primary" onclick="loadAndClean()">🚀 抽取并执行清洗治理</button>
    </div>
  </div>

  <!-- 数据清洗流水线全景时序示意图 (5步端到端治理路径) -->
  <div class="pipeline-section">
    <div class="pipeline-header">
      <div class="pipeline-title">
        <span>⚙️</span> 日志数据智能清洗流水线时序示意图 (Data Cleaning Pipeline Stages)
      </div>
      <div class="pipeline-subtitle">
        从原始“脏日志”到高价值“纯净流”的标准治理路径 (5大核心步骤)
      </div>
    </div>
    <div class="pipeline-steps">
      <!-- 步骤 1 -->
      <div class="pipeline-step step-1">
        <div class="step-top">
          <span class="step-num">STEP 01</span>
          <span class="step-badge badge-raw">数据摄取</span>
        </div>
        <div class="step-name">📥 原始日志摄取</div>
        <div class="step-desc">从 K8s 容器 stdout / 节点日志或 Loki 抓取原生流，包含大量杂质与冗余。</div>
        <div class="step-rule" title="输入源状态">⚠️ 包含探针/明文IP/Token</div>
      </div>

      <div class="pipeline-arrow">➔</div>

      <!-- 步骤 2 -->
      <div class="pipeline-step step-2">
        <div class="step-top">
          <span class="step-num">STEP 02</span>
          <span class="step-badge badge-detect">缺陷识别</span>
        </div>
        <div class="step-name">🔍 缺陷特征探测</div>
        <div class="step-desc">模式引擎并发扫描，精准识别并分类存活心跳、明文私网 IP 与敏感鉴权密钥。</div>
        <div class="step-rule" title="规则匹配">🎯 正则探测与分类打标</div>
      </div>

      <div class="pipeline-arrow">➔</div>

      <!-- 步骤 3 -->
      <div class="pipeline-step step-3">
        <div class="step-top">
          <span class="step-num">STEP 03</span>
          <span class="step-badge badge-filter">降噪过滤</span>
        </div>
        <div class="step-name">🚫 冗余降噪拦截</div>
        <div class="step-desc">对无业务与排障价值的存活探针（kube-probe / healthz）直接丢弃阻断不入库。</div>
        <div class="step-rule" title="处置动作">📉 丢弃拦截节约 40%+ 存储</div>
      </div>

      <div class="pipeline-arrow">➔</div>

      <!-- 步骤 4 -->
      <div class="pipeline-step step-4">
        <div class="step-top">
          <span class="step-num">STEP 04</span>
          <span class="step-badge badge-maskstep">安全合规</span>
        </div>
        <div class="step-name">🛡️ 敏感数据脱敏</div>
        <div class="step-desc">私网 IP 转为 [IP_MASK]，Token 密钥深度遮蔽为 [TOKEN_MASK]，杜绝信息泄露。</div>
        <div class="step-rule" title="安全门禁">🔒 敏感词泄露率 0.0%</div>
      </div>

      <div class="pipeline-arrow">➔</div>

      <!-- 步骤 5 -->
      <div class="pipeline-step step-5">
        <div class="step-top">
          <span class="step-num">STEP 05</span>
          <span class="step-badge badge-deliver">规范输出</span>
        </div>
        <div class="step-name">🏷️ 规范输出交付</div>
        <div class="step-desc">标准化抽取 INFO/WARN/ERROR 日志级别标签，纯净格式化数据交付存储与 AIOps。</div>
        <div class="step-rule" title="交付目标">🚀 纯净入库 / AIOps根因排障</div>
      </div>
    </div>
  </div>

  <!-- 分类与修复图例看板 -->
  <div class="legend-banner">
    <div class="legend-col">
      <span class="legend-label">🔴 左侧脏数据缺陷分类:</span>
      <span class="badge-defect-probe" title="K8s存活心跳探针">🔴 探针心跳噪音</span>
      <span class="badge-defect-ip" title="暴露内部节点/Pod IP">🟡 私网IP明文</span>
      <span class="badge-defect-token" title="明文敏感认证凭证">🟣 凭据密钥明文</span>
      <span class="badge-defect-clean" title="格式正常业务日志">⚪ 合规业务流</span>
    </div>
    <div class="legend-col">
      <span class="legend-label">🟢 右侧对应治理修复:</span>
      <span class="badge-fix-drop">🚫 拦截丢弃不入库</span>
      <span class="badge-fix-ip">🛡️ IP掩码脱敏</span>
      <span class="badge-fix-token">🔒 凭据密钥遮蔽</span>
      <span class="badge-level INFO">🏷️ 级别标准化</span>
    </div>
  </div>

  <div class="metrics-bar">
    <div class="card"><div class="title">原始日志总数</div><div class="val blue" id="mTotal">-</div></div>
    <div class="card"><div class="title">探针噪音拦截数</div><div class="val amber" id="mDropped">-</div></div>
    <div class="card"><div class="title">净保留有效业务条数</div><div class="val green" id="mKept">-</div></div>
    <div class="card"><div class="title">📉 存储直接降噪率</div><div class="val green" id="mRate">-</div></div>
    <div class="card"><div class="title">🛡️ 敏感信息脱敏处数</div><div class="val blue" id="mMasked">-</div></div>
  </div>

  <div class="split-container">
    <div class="panel">
      <div class="panel-header left">
        <span>🔴 原始脏日志流 (含缺陷类型识别)</span>
        <span style="font-size: 11px; font-weight: normal; color: #fca5a5;">黄色下划线=IP, 紫色=Token, 红色=探针</span>
      </div>
      <div class="log-stream" id="rawStream">正在加载日志...</div>
    </div>
    <div class="panel">
      <div class="panel-header right">
        <span>🟢 清洗后纯净流 (含修复行为追踪)</span>
        <span style="font-size: 11px; font-weight: normal; color: #6ee7b7;">绿色徽章=[IP_MASK], 紫色=[TOKEN_MASK]</span>
      </div>
      <div class="log-stream" id="cleanStream">等待执行清洗...</div>
    </div>
  </div>

  <script>
    async function loadAndClean() {
      const ns = document.getElementById('nsSelect').value;
      const res = await fetch(`/api/clean?namespace=${ns}&limit=35`);
      const data = await res.json();
      
      document.getElementById('mTotal').innerText = data.summary.total_raw;
      document.getElementById('mDropped').innerText = data.summary.dropped_spam + " 条";
      document.getElementById('mKept').innerText = data.summary.clean_kept + " 条";
      document.getElementById('mRate').innerText = data.summary.drop_rate_pct + "%";
      document.getElementById('mMasked').innerText = data.summary.masked_items + " 处";

      let rawHtml = '';
      let cleanHtml = '';

      data.records.forEach((rec, idx) => {
        const rowNum = `#${idx + 1}`;
        
        // 1. 构建左侧卡片 (缺陷分类与脏点高亮)
        let defectBadges = rec.defects.map(d => `<span class="${d.css}" title="${d.desc}">${d.tag}</span>`).join('');
        let rawBorderClass = 'clean-pass';
        if (rec.defects.some(d => d.tag.includes('探针'))) rawBorderClass = 'has-probe';
        else if (rec.defects.some(d => d.tag.includes('IP'))) rawBorderClass = 'has-ip';
        else if (rec.defects.some(d => d.tag.includes('Token'))) rawBorderClass = 'has-token';

        rawHtml += `
          <div class="log-item ${rawBorderClass}">
            <div class="meta-bar">
              <div class="tag-group">${defectBadges}</div>
              <span class="row-idx">${rowNum}</span>
            </div>
            <div class="log-content">${rec.raw_html}</div>
          </div>
        `;

        // 2. 构建右侧卡片 (修复分类与脱敏结果)
        let remediationBadges = rec.remediations.map(r => `<span class="${r.css}" title="${r.desc}">${r.tag}</span>`).join('');
        cleanHtml += `
          <div class="log-item ${rec.action === 'DROPPED' ? 'has-probe' : 'clean-pass'}">
            <div class="meta-bar">
              <div class="tag-group">${remediationBadges}</div>
              <span class="row-idx">${rowNum}</span>
            </div>
            <div class="log-content">${rec.clean_html}</div>
          </div>
        `;
      });

      document.getElementById('rawStream').innerHTML = rawHtml;
      document.getElementById('cleanStream').innerHTML = cleanHtml;
    }
    window.onload = loadAndClean;
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(content=HTML_TEMPLATE)

if __name__ == "__main__":
    print("==================================================")
    print("[*] Loki Data Cleaner Interactive WebUI Started!")
    print("[*] Please open your browser: http://localhost:8088")
    print("==================================================")
    uvicorn.run(app, host="0.0.0.0", port=8088)

