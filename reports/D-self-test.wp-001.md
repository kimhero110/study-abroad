# WP-001 D 阶段自测报告（数据覆盖与质量）

**日期：** 2026-10-07 ｜ **工作包：** WP-001 ｜ **当前阶段：** D ｜ **结论：** D 未通过（self-test 发现 Must 验收不达标）

## 一、执行的测试

| 测试 | 命令 | 结果 |
|---|---|---|
| 存储/幂等 MS-101 | `python3 tests/test_ms101_storage.py` | ALL PASS |
| 匹配规则 MS-105 | `python3 tests/test_ms105_matching.py` | ALL PASS |
| 引用强制 REQ-004（新增） | `python3 tests/test_req004_citation.py` | ALL PASS |
| 数据质量/覆盖证据 | `python3 scripts/data_quality_report.py` | 见 `reports/data_quality.json` |
| 幂等证据 | `python3 scripts/idempotency_check.py` | THR-IDEM pass（delta=0） |
| 匹配零 LLM 审计 | `python3 scripts/audit_nollm.py` | THR-NOLLM pass（matching/ 仅 stdlib） |

## 二、阈值对照（C 门预声明）

| 阈值 | 目标 | 实测 | 判定 |
|---|---|---|---|
| THR-DATA-1 项目数 ≥60 | ≥60 | 192 | ✅ |
| THR-DATA-1 关键字段完整率 | ≥0.95 | gpa_requirements **0.094** | ❌ |
| THR-CITE 引用覆盖率 | =1.0 | 1.0 | ✅ |
| THR-NOLLM 匹配零 LLM | =0 命中 | 0 | ✅ |
| THR-IDEM 双跑增量 | =0 | 0 | ✅ |
| REQ-003 三档各 ≥3 | 每个常规用例 | E-001 reach=0；E-004 reach=0/match=0 | ❌ |

## 三、根因

1. **gpa_requirements 抽取严重缺失**：192 个真实项目中仅 18 个（9.4%）带有分档均分要求；139 个项目 `school_list_req` 为空。匹配引擎对无 tier 数据项目一律不入档（冻结规则），导致大量项目无法参与分档。
2. **地区/院校覆盖缺口**：L1 项目仅 6 所英国校（UCL/南安/格拉/帝国/曼大/KCL），**港三（HKU/CUHK/HKUST）与新二（NUS/NTU）项目数为 0**，与 PRD In Scope「港三+新二+英国 G5/王爱曼华」不符。
3. **reach 档为空的结构原因**：当前可入档项目以 UCL 自有名单与少数有分档数据的项目为主，对 985/88 强背景全部落入 match/safety，无法产生冲刺档。

## 四、对 A-001 的影响

PRD A-001 证伪条件：「60 项目中 >30% 无法采到要求 → 立即回 P」。当前 192 个项目中仅 36.98%（71/192）可入档，缺口远超 30%，**A-001 已被证伪**。

## 五、D 门结论

D 阶段实现未满足 REQ-001（字段完整率）与 REQ-003（三档各 ≥3），不满足进入 C 的条件。按 PRDCA，此项属计划层问题（数据源可行性假设失效），应**返回 P** 修订计划：要么缩减/重定义覆盖目标，要么单独立项「数据覆盖与质量」工作包（含 HK/SG 项目采集 + gpa_requirements 抽取补齐）。

## 六、建议

新建工作包 **WP-002：数据覆盖与质量**（回 P 立项），范围：
- L1 补齐港三 + 新二项目采集适配器
- 提升 gpa_requirements 抽取完整率至 ≥0.95（重点：英式 2:1/2:2 与院校 list 的官方折算页）
- 输入 `data/tier_map.json` 分档定义
- 完成后重跑 `scripts/data_quality_report.py` 与 E 用例集，再启 C 门
