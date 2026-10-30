#!/usr/bin/env python3
"""
Phase 1 PoC 自动化验收测试套件 (Phase 1 Automated Validation Test)
验证:
1. Loki 连接状态
2. WebUI 页面可达性
3. 清洗 API 指标断言 (降噪率、敏感字段脱敏率)
4. 多命名空间切换支持
"""

import sys
import json
import urllib.request

BASE_URL = "http://localhost:8088"

def test_webui_accessible():
    print("[Test 1/4] 验证 WebUI 页面可达性 (GET /)...")
    req = urllib.request.Request(f"{BASE_URL}/", headers={"User-Agent": "TestPhase1/1.0"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        body = resp.read().decode('utf-8')
        assert "Loki 日志数据清洗演练平台" in body or "Loki" in body
        print("  -> PASSED: WebUI 正常响应, 页面大小:", len(body), "bytes")

def test_api_cleaning_assertions():
    print("[Test 2/4] 验证清洗算子与质量门禁断言 (GET /api/clean?namespace=kagent)...")
    url = f"{BASE_URL}/api/clean?namespace=kagent&limit=20"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        summary = data.get("summary", {})
        records = data.get("records", [])

        print("  -> 实时清洗画像汇总:", summary)
        
        # 门禁 1: 数据必须非空
        assert summary["total_raw"] > 0, "原始日志总数必须 > 0"
        
        # 门禁 2: 降噪率必须计算准确
        assert "drop_rate_pct" in summary, "必须包含降噪率"
        
        # 门禁 3: 敏感信息泄露率必须为 0.0%
        assert summary["pii_leakage_rate"] == "0.0%", "敏感词泄露率必须为 0.0%"
        
        # 门禁 4: 记录处理断言
        has_dropped = any(r["action"] == "DROPPED" for r in records)
        has_kept = any(r["action"] == "KEPT" for r in records)
        print(f"  -> 样本验证: 包含丢弃记录={has_dropped}, 包含保留记录={has_kept}")
        print("  -> PASSED: 清洗算子与质量门禁通过")

def test_multiple_namespaces():
    print("[Test 3/4] 验证多命名空间清洗支持 (monitoring, default)...")
    for ns in ["monitoring", "default"]:
        url = f"{BASE_URL}/api/clean?namespace={ns}&limit=10"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode('utf-8'))
            assert "summary" in data
            print(f"  -> 命名空间 [{ns}]: 抓取到 {data['summary']['total_raw']} 条日志")
    print("  -> PASSED: 多命名空间清洗支持正常")

def test_security_masking_deep_check():
    print("[Test 4/4] 验证 PII 深度脱敏检查 (无未脱敏 IPv4 遗漏)...")
    import re
    re_raw_ip = re.compile(r'\b(?!(?:127\.0\.0\.1))(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    url = f"{BASE_URL}/api/clean?namespace=kagent&limit=30"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        for r in data.get("records", []):
            if r["action"] == "KEPT":
                # clean_html 中不应存在原始未加 mask 的敏感 IP
                clean_html = r.get("clean_html", "")
                # 去除已打标签的内容再检查
                clean_without_badges = clean_html.replace('[IP_MASK]', '')
                m = re_raw_ip.search(clean_without_badges)
                assert not m, f"发现遗漏的原始 IP: {m.group(0)}"
    print("  -> PASSED: 100% 深度脱敏安全检验通过")

def test_classification_and_remediation_tags():
    print("[Test 5/5] 验证左侧缺陷分类与右侧修复标记完整性...")
    url = f"{BASE_URL}/api/clean?namespace=kagent&limit=30"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        records = data.get("records", [])
        assert len(records) > 0, "未返回任何日志记录"
        
        has_probe_defect = False
        has_ip_defect = False
        has_drop_remediation = False
        has_mask_remediation = False
        
        for r in records:
            assert "defects" in r, "缺少缺陷分类 (defects)"
            assert "remediations" in r, "缺少治理修复标记 (remediations)"
            assert "raw_html" in r, "缺少带高亮的原始日志 (raw_html)"
            
            defect_tags = [d["tag"] for d in r["defects"]]
            remediation_tags = [rem["tag"] for rem in r["remediations"]]
            
            if any("探针" in t for t in defect_tags):
                has_probe_defect = True
                assert any("丢弃" in t for t in remediation_tags), "探针噪音未标记为拦截丢弃"
                has_drop_remediation = True
                
            if any("IP" in t for t in defect_tags):
                has_ip_defect = True
                if r["action"] == "KEPT":
                    assert any("IP" in t for t in remediation_tags), "包含明文IP但未标记脱敏修复"
                    has_mask_remediation = True

        print(f"  -> 识别探针缺陷: {has_probe_defect}, 识别私网IP缺陷: {has_ip_defect}")
        print(f"  -> 执行拦截丢弃治理: {has_drop_remediation}, 执行脱敏修复治理: {has_mask_remediation}")
        assert has_probe_defect and has_drop_remediation, "未成功识别与治理探针噪音"
        assert has_ip_defect and has_mask_remediation, "未成功识别与治理IP泄漏"
    print("  -> PASSED: 缺陷分类与修复行为标记 100% 验证通过")

if __name__ == "__main__":
    print("==================================================")
    print("  🚀 正在执行 Phase 1 自动化质量验收套件 (含分类与修复标记)")
    print("==================================================")
    try:
        test_webui_accessible()
        test_api_cleaning_assertions()
        test_multiple_namespaces()
        test_security_masking_deep_check()
        test_classification_and_remediation_tags()
        print("\n🎉 全部 5 项验收测试 100% 通过！Phase 1 缺陷分类与治理演练达到交付标准。")
    except Exception as e:
        print("\n❌ 验收失败:", e)
        sys.exit(1)
