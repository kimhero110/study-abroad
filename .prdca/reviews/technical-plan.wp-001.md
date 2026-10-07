# Technical Plan — WP-001 留学信息服务平台 MVP（V0.3）

**工作包：** WP-001 ｜ **日期：** 2026-10-02

## Stage

P（计划）→ D 实施依据。

## Architecture Summary

权威数据底座先行：L0 教育部认可名单 + L1 院校官方项目要求，纯规则选校。**规则优先，LLM 只做抽取（OpenAI 兼容可配置）；无引用不推荐；采集幂等**。案例层（L3）与向量检索整体移至 WP-002。

```text
种子 URL 清单（人工维护：监管网 + 各校项目页）
   │
   ▼
collectors/            限速抓取（≥1s/请求），raw HTML 快照落盘
   │                   data/raw/{source}/{YYYY-MM}/
   ▼
pipeline/extract       LLM 抽取结构化字段（OpenAI 兼容客户端，JSON Schema 约束）
   │                   数字字段规则校验，不过 → quarantine
   ▼
storage/catalog.sqlite3  recognized_schools / programs / collect_state / quarantine
   │                   （WAL + busy_timeout + 写重试；自然键 upsert）
   ▼
matching/              hard_filter（纯规则）→ margin 分档（纯规则）
   │                   全程无 LLM、无向量检索
   ▼
api/ (FastAPI, 127.0.0.1)   /api/match  /api/programs/{id}  /api/schools/recognition
   │
   ├─ 本地访问：web/ 单页
   └─ 公网验证：cloudflared tunnel → HTTPS URL
```

## Components

| Component | Responsibility | Owner | Notes |
|---|---|---|---|
| collectors/moe_recognition | 教育部涉外监管网认可名单采集（L0） | primary | D 阶段首个验证任务 |
| collectors/program_page | 院校项目页采集（L1） | primary | 种子清单 + 逐校适配器 |
| pipeline/extract | LLM 结构化抽取 | primary | OpenAI 兼容客户端 + JSON Schema + 重试 |
| pipeline/validate | 规则校验（均分 0-100、IELTS 0-9、日期 ISO、学费正数） | primary | 不过 → quarantine |
| storage | SQLite 目录库 | primary | WAL、自然键 upsert、stale 标记 |
| matching/hard_filter | 硬性要求过滤（纯规则） | primary | 可单测 |
| matching/tier | margin 分档（纯规则） | primary | 冻结规则见「分档规则」节 |
| api | 查询/计算型 HTTP 服务（无管理端点） | primary | FastAPI，绑 127.0.0.1 |
| web | 单页 UI | primary | 原生 HTML/JS，无构建链 |
| llm_client | OpenAI 兼容 LLM 客户端 | primary | base_url/api_key/model 环境变量 |

## Data Flow

```text
[监管网/官网项目页] -> [限速采集+快照] -> [LLM抽取+规则校验] -> [SQLite 状态机]
   -> [hard_filter -> margin 分档] -> [API] -> [Web UI] -> [cloudflared 公网验证]
```

## Interfaces

| Interface | Producer | Consumer | Contract |
|---|---|---|---|
| recognized_schools 表 | collectors/moe | api/matching | school_id PK；认可状态 + 来源 |
| programs 表 | pipeline | matching/api | program_id PK；recognized_school FK |
| POST /api/match | api | web | 见 API 契约节 |
| GET /api/schools/recognition?name= | api | web | 认可状态查询 |

## API 契约

`POST /api/match`

```json
请求: {"undergrad_tier":"211","gpa":85.5,"ielts":6.5,"target_field":"cs"}
响应: {
  "tiers": {
    "reach":  [{"program_id":"...","university":"...","program":"...",
                "recognized": true,
                "reasons":["..."],"citations":[{"type":"program_page","ref":"...","url":"...","snapshot_ref":"..."}]}],
    "match":  [...],
    "safety": [...]
  },
  "data_sufficiency": "ok | insufficient",
  "case_layer": "not_available_in_mvp",
  "notice": "本结果全部基于官方公开信息，仅供参考；申请要求以学校官网为准。录取案例数据建设中。",
  "generated_at": "..."
}
```

- `data_sufficiency=insufficient` 时三档均为空数组且附差距说明（REQ-005）
- 任何推荐条目 `citations` 非空，服务端强制丢弃空引用推荐并记录（REQ-004）
- 每条推荐携带该院校教育部认可状态（`recognized` 字段，来自 L0 关联）

`GET /api/schools/recognition?name=香港大学` 冻结应答契约：

- **命中**：`{"name":"...","region":"hk","found":true,"recognized":true,"source_url":"...","snapshot_ref":"...","fetched_at":"..."}`
- **未命中**：`{"name":"...","found":false,"recognized":null,"message":"该院校未出现在教育部认可名单中（未收录不等于不认可），请至教育部教育涉外监管信息网核实","list_url":"<名单检索页URL>"}`

`recognized_schools` 只存正面记录（教育部名单是正面清单，不存在可采集的「不认可」记录）；系统**永不输出**「该校不被认可」的否定陈述。

## LLM 客户端（OpenAI 兼容，REQ-009）

```python
# 配置全部来自环境变量，切换供应商零代码改动
LLM_BASE_URL   # 如 https://api.deepseek.com 或 http://localhost:11434/v1
LLM_API_KEY
LLM_MODEL      # 如 deepseek-chat 或 qwen2.5:14b
```

- 调用协议：OpenAI `POST /chat/completions`，`response_format=json_object`
- Fallback：主端点失败 → 备用端点（`LLM_FALLBACK_BASE_URL` 等一组）；均不可用 → **暂停交付并上报人类**，不允许无质检数据入库
- matching/ 目录禁止引用该客户端（THR-NOLLM 静态审计）

## Data Plan

### Data Sources

| Source | Type | Access Method |
|---|---|---|
| 教育部教育涉外监管信息网（L0） | HTML | 限速 HTTP GET，raw 快照 |
| 各校官网项目页（L1） | HTML | 同上，种子 URL 清单 + 逐校适配器 |
| LLM API | 抽取服务 | OpenAI 兼容，可配置 |

### Data Objects

**recognized_schools**（L0）：`school_id`(PK) `name_zh` `name_en` `region`(hk/sg/uk) `recognized`(bool) `source_url` `snapshot_ref` `fetched_at` `content_hash`

**programs**（L1）：`program_id`(PK) `school_id`(FK→recognized_schools) `university` `name` `field` `degree` `duration_months` `tuition_amount` `tuition_currency` `gpa_requirements`(json: `[{"tier":"C9|985|211|shuangyiliu|shuangfei|overseas","min_gpa":83}]`) `school_list_req`(json) `ielts_req`(json: `{"overall":6.5,"min_sub":6.0}`) `toefl_req`(json 同构) `deadlines`(json: `[{"round":1,"close_date":"..."}]`) `intake_year` `source_url` `snapshot_ref` `source_excerpts`(json: 关键数字字段→原文片段) `fetched_at` `content_hash` `stale`(bool)

**collect_state**：`source_id` `last_cursor` `status` `updated_at`

**quarantine**：校验失败的抽取结果 + 原因码

**自然键与更新语义**：programs 以 `(university, name, intake_year)` upsert（content_hash 变化原位更新，不产生重复行）；recognized_schools 以 `(name_zh, region)` upsert。刷新周期：申请季（9-12月）每月全量重采；`fetched_at` 距今 >60 天标记 `stale=true`，API 响应明示。

### 院校层次分档定义（冻结）

| tier 枚举 | 含义 | 判定依据 |
|---|---|---|
| C9 | 九校联盟 | 固定名单（9 所） |
| 985 | 985 工程（不含 C9） | 教育部名单 |
| 211 | 211 工程（不含 985） | 教育部名单 |
| shuangyiliu | 双一流（不含 985/211） | 教育部名单 |
| shuangfei | 其余公办本科 | 兜底 |
| overseas | 海外本科 | QS50→985，QS100→211，其余→shuangfei |

判定表存 `data/tier_map.json`（人工维护种子 + 采集扩充），无法判定的学校 → shuangfei 并记录待人工复核清单。

### Quality Rules

| Rule | Metric | Threshold | Blocking |
|---|---|---|---|
| 数字字段范围校验 | quarantine 率 | ≤10% | No（超阈值告警复盘） |
| 抽取准确率（人工抽样） | 字段级一致率 | ≥95%（programs 30，按适配器分层） | Yes |
| 引用可访问性 | URL 200 率 | ≥90%；不可达者快照可用率 100% | Yes |
| 采集幂等 | 双跑行数增量 | 0 | Yes |
| 种子清单对账 | 期望 vs 实际归属 | 60/60 有归属；单校 quarantine ≤50% | Yes |
| L0 覆盖 | 目标地区认可院校覆盖率 | 100% | Yes |

### Metadata and Lineage

每条记录含 `source_url` + `snapshot_ref` + `fetched_at` + `content_hash`；programs 关键数字字段另存 `source_excerpts`（字段→原文片段），人工核验无需翻页。raw 快照按 `data/raw/{source}/{date}/` 留存；URL 不可达时 UI 回落展示快照。

## 分档规则（确定性，冻结）

匹配引擎全部为确定性规则，无 LLM、无向量检索（THR-NOLLM）。

**Step 1 硬过滤（hard_filter）**：剔除任一不满足的项目：
- 用户院校层次在 `school_list_req` 名单外（若该项目有名单要求）
- 用户均分 < `gpa_requirements[用户tier].min_gpa - 3`（允许 3 分内冲刺，超过剔除）
- 用户语言成绩 < `ielts_req.overall` 或单项 < `min_sub`（未考语言 → 标「语言待考」，不剔除但封顶 match）

**Step 2 分档**：`margin = 用户均分 - 该项目对用户 tier 的 min_gpa`
- **safety**：margin ≥ +5 且语言达标
- **match**：0 ≤ margin < +5
- **reach**：-3 ≤ margin < 0
- 语言未达标者最高 match；无该 tier 要求数据的项目不入档（避免臆断）

**Step 3 拒绝**：三档合计为空 → `data_sufficiency=insufficient` + 说明差距（REQ-005）

**案例纠偏说明**：L3 案例层移至 WP-002，MVP 分档完全基于官方要求；所有推荐响应携带 `case_layer: "not_available_in_mvp"` 与建设中标注。专家盲评（THR-EXPERT）把关无案例时的分档质量。

**E-005~E-010 卡线用例**对应边界：margin=±5/0/-3、语言单项卡线、tier 要求缺失。

## AI/RAG Plan

### AI Use Case

- **抽取**（唯一用途）：项目页/监管名单文本 → 结构化 JSON（LLM，JSON Schema 约束）
- **明确不做**：LLM 不参与匹配决策、不生成数字字段、不生成推荐文案（模板文案）；MVP 无向量检索（随案例层移至 WP-002）

### Model Strategy

- 客户端：OpenAI 兼容可配置（REQ-009）；主端点 + 备用端点双配置
- Fallback：双端点均不可用 → 暂停交付并上报人类
- 隐私：MVP 无用户数据存储；背景输入不持久化

### Evaluation Set（预声明，C 阶段冻结于 tests/fixtures/）

| Case ID | Input | Expected Behavior |
|---|---|---|
| E-001 | 985/88/IELTS7.0/商科 | 三档均有推荐，引用齐全，分档与规则手算一致 |
| E-002 | 双非/78/IELTS6.0/CS | 保底为主或明确说明 |
| E-003 | 双非/70/无语言/商科 | insufficient，零推荐 |
| E-004 | 目标方向无项目数据 | 明确说明无数据 |
| E-005~E-010 | 边界组合（margin 卡线/语言单项卡线/tier 要求缺失） | 分档行为与冻结规则逐步一致 |
| E-011 | 查询港大（命中）/某不在名单院校（未命中） | 港大：recognized=true 带来源；未命中校：found=false + 「未收录≠不认可」说明 + 名单检索链接，**不出现否定陈述** |

### Quality Metrics

| Metric | Target | Blocking |
|---|---|---|
| 抽取字段准确率 | ≥95%（programs 30 人工抽样，字段级，按适配器分层） | Yes |
| 推荐引用覆盖率 | 100% | Yes |
| 编造推荐数（拒绝场景） | 0 | Yes |
| L0 认可查询正确率 | 100%（目标院校全量核对） | Yes |

## Security and Permission Approach

- API 绑 127.0.0.1；公网仅经 cloudflared 隧道（Quick Tunnel 随机域名，验证后关闭）
- 无账号体系（验证期）；密钥走 `.env`，不进 git
- 采集限速 ≥1s/请求，遵守 robots.txt，仅公开页面
- 输入参数全部参数化；Web 输出全部转义防 XSS
- **隧道模式加固**（验证窗口开启时生效，纳入 TST-010 检查项）：
  - 隧道模式禁用 FastAPI `/docs`、`/redoc`、`/openapi.json`
  - 公网访问需一次性分享 token（URL query 参数，验证批次结束即轮换）
  - API 速率限制：30 次/分钟/IP
  - 暴露面仅为查询与匹配接口（GET /api/schools/*、GET /api/programs/*、POST /api/match 计算型接口）；无管理端点

## Deployment（CR-001）

- **本地**：`uvicorn api:app --host 127.0.0.1 --port 8322`（默认交付形态）
- **公网验证**：`cloudflared tunnel --url http://127.0.0.1:8322`（Quick Tunnel，免费 HTTPS 随机域名）；验证窗口期开启，结束即关
- **非目标**：Workers/D1 云原生（产品化阶段单独立项评估）

## Traceability

| Requirement | Planned Change | Predeclared Test | Evidence Artifact |
|---|---|---|---|
| REQ-001 | CHG-001 schema+采集 | TST-001 项目数/字段完整率脚本 | reports/data_quality.json |
| REQ-002 | CHG-002 L0 采集 | TST-002 认可名单覆盖率核对 | reports/recognition_coverage.json |
| REQ-003 | CHG-003 matching | TST-003 E2E 用例集（分档与规则手算一致） | reports/e2e.json |
| REQ-004 | CHG-003/004 | TST-004 引用覆盖率断言 + 抽样核验 | reports/citation_check.json |
| REQ-005 | CHG-003 | TST-005 拒绝用例集断言 | reports/e2e.json |
| REQ-006 | CHG-004 api+web | TST-006 步骤化人工核验清单（非执行角色签字，含 notice 可见断言） | reports/manual_e2e.md |
| REQ-007 | CHG-001 | TST-007 双跑行数断言 | reports/idempotency.json |
| REQ-008 | CHG-003 | TST-008 静态审计（冻结三式模式） | reports/audit.json |
| REQ-009 | CHG-005 llm_client | TST-009 双供应商端点冒烟（配置切换零代码） | reports/llm_smoke.json |
| REQ-010 | CHG-006 tunnel | TST-010 隧道公网完成 S-001 记录 | reports/tunnel_e2e.md |
| REQ-003 | CHG-003 | TST-011 专家盲评（rubric 3 维各 1-5，单项≥3 总分≥10 合格，≥70%） | reports/expert_blind_review.md |

## Threshold Declaration（C 门数值准则，P 冻结）

见 `.prdca/reviews/thresholds.wp-001.json`：THR-DATA-0（L0 覆盖 100%）、THR-DATA-1（L1 项目库）、THR-EXTRACT（programs 30 字段级 ≥0.95）、THR-E2E（=1.0）、THR-EXPERT（≥0.70）、THR-CITE（=1.0）、THR-REJECT（=1.0）、THR-IDEM（=0）、THR-SEED（对账 60/60）、THR-NOLLM（=0，冻结模式）、THR-LLMCONF（双端点冒烟）、THR-DEFECT（P0/P1=0）。

## Delivery Decomposition（L2）

见 `.prdca/evidence/decomposition.wp-001.json`：N-DATA（schema+状态机）→ N-L0（监管名单采集）与 N-COLLECT（项目采集）并行 → N-EXTRACT（抽取管线）→ N-MATCH（纯规则匹配）→ N-SERVE（API+UI+Tunnel）。N-DATA 为 covered 前置。

## Delivery Plan and Roles

- 执行者：primary AI（代码/采集/测试）；人类：抽样核验（THR-EXTRACT）、专家盲评（TST-011，预算 2h）、TST-006 步骤签字（预算 0.5h）、L0 名单一次性人工录入（仅监管网采集兜底触发时，预算 2h）、最终验收
- 里程碑（CR-001 后 ~28h 机算 + 4.5h 人工）：MS-101 schema+状态机（4h）→ MS-102 L0 名单采集（4h）→ MS-103 三校项目采集跑通（5h）→ MS-104 抽取管线（5h）→ MS-105 matching+单测（4h）→ MS-106 API+UI+Tunnel（4h）→ MS-107 扩量至 60 项目（2h）→ MS-108 全量 E2E + 人工评审（专家盲评 2h + TST-006 0.5h，人类排期）
- 项目目录：`study-abroad/`（workspace 下新建）

## Risks and Fallbacks

| Risk | Fallback |
|---|---|
| 监管网页面结构特殊/采集失败 | 该来源失败单独隔离；触发 L0 一次性人工录入兜底（人类职责已排期，量小）；结构不可采且无人工兜底 → 回 P |
| 某校适配器批量失败 | 种子对账暴露缺口（THR-SEED）；缩范围需回 P |
| LLM 双端点失效 | 暂停交付并上报人类裁定 |
| 隧道大陆不可达 | 验证期替代：本地演示/国内穿透；不阻断本地交付（A-005） |

## Review Readiness

- [x] Architecture supports scope
- [x] Major assumptions listed（A-001~A-005）
- [x] Fallbacks defined
- [x] Operations impact considered
- [x] Requirement-to-change mapping defined
- [x] Independent review packet is bounded and reproducible

## V0.4 数据覆盖与质量修复（A-001 证伪后回 P）

### 触发与证据

D 阶段自测（`reports/D-self-test.wp-001.md`、`reports/data_quality.json`）：192 个真实项目中可入档仅 71（36.98%）；`gpa_requirements` 完整率 0.094；港三/新二项目为 0；REQ-003 三档各 ≥3 不成立。PRD A-001 证伪，回 P。

### 目标院校覆盖分母（冻结，14 校）

港三 HKU/CUHK/HKUST ＋ 新二 NUS/NTU ＋ 英国 G5 牛津/剑桥/帝国理工/UCL/LSE ＋ 王爱曼华 KCL/爱丁堡/曼彻斯特/华威。某校计入覆盖当且仅当 cs 或 business 方向入库项目 ≥3。覆盖率 = 达标校数 / 14 ≥ 0.8（THR-COVERAGE）。格拉、南安等为扩展项，不计入分母。

### 分档数据策略（REQ-011 / THR-GPA）

分档依据来源分层，全部要求官方可溯源：

1. **英国校**：抓取各校官方「中国申请者入学要求」国家页（China country page），提取 2:1 / 2:2 → 中国院校层次（985/211/双非等）均分折算；写入 `gpa_requirements` 或 `school_list_req`。UCL 沿用 `ucl_custom_list`（77 所自有名单）。
2. **港/新校**：项目页通常写明「recognised bachelor's degree, min GPA x/4.0 或 x%」；抽取出对内地申请者的均分门槛；无明示分档者记录 `school_list_req` 或标注数据缺口。
3. **院校层次定义**：`data/tier_map.json`（人工维护种子 + 采集扩充），无法判定 → `shuangfei` 并记待复核清单（沿用技术方案既有定义）。
4. **抽取质量门**：折算/名单数值必须带 `source_excerpts` 原文片段；`validate_program` 扩展校验「有推荐价值但缺分档依据」的告警码（不阻断入库但计入 THR-GPA 分母）。

### 采集器新增

- `collectors/hk_programs.py`、`collectors/sg_programs.py`：港三 + 新二项目列表/详情适配器（复用 `uk_common` 的 fetch→extract→validate→upsert 管线）。
- `collectors/uk_common.py`：扩展 `SCHOOLS` 增加 lse/edinburgh/warwick/oxford/cambridge 配置与 lister。
- `collectors/gpa_china.py`：各校官方中国折算页采集与结构化（2:1/2:2 折算 + 名单）。

### 新增阈值与追溯

| Requirement | Planned Change | Predeclared Test | Evidence Artifact |
|---|---|---|---|
| REQ-001 覆盖 | CHG-007 HK/SG + UK 采集 | TST-012 覆盖率统计（THR-COVERAGE） | reports/data_quality.json |
| REQ-011 分档可得 | CHG-008 gpa_china + tier_map | TST-013 可得率统计（THR-GPA） | reports/data_quality.json |
| REQ-003 三档 | CHG-003 复用 | TST-003 E 用例集（每档 ≥3） | reports/e2e.json |

### 里程碑（BASE-103）

MS-109 港三+新二采集适配器（16h）→ MS-110 英国目标校补采（12h）→ MS-111 分档依据补齐（20h）；MS-112 data/tier_map.json（6h）；MS-113 覆盖/质量证据重跑 + E 用例集（10h）。

### 新增风险

| Risk | Fallback |
|---|---|
| 港/新官网 JS 渲染或反爬，采集不可行 | browser_fetch 渲染兜底；仍失败则该校出分母并在 PRD 记录；覆盖率目标按冻结规则调整需再次回 P |
| 英国校中国折算页结构不一、无统一 2:1/2:2 折算 | 逐校适配器；无官方折算者该项目不入「可推荐」并计入 THR-GPA 缺口，不臆造 |
| tier_map 判定争议 | 无法判定 → shuangfei + 待复核清单；争议校人工仲裁 |
