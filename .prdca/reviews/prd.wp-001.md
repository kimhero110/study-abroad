# PRD — 留学信息服务平台 MVP（港新英一年制硕士 · 权威数据底座 + AI 选校定位）

**工作包：** WP-001 ｜ **宏观里程碑：** M-SA-MVP ｜ **版本：** V0.3（CR-001 + 三轮 R 修订）｜ **日期：** 2026-10-02

**V0.2 变更（CR-001，major）：** 数据源分层调整——新增 L0 监管认可名单，L3 录取案例层整体移至 WP-002；LLM 客户端改为 OpenAI 兼容可配置；部署采用本地运行 + Cloudflare Tunnel 公网验证。

## Stage

P（计划）→ 交付 MVP：本地可运行 + Tunnel 公网可访问的「院校认可查询 + 背景输入 → 选校梯度清单（全官方引用）」。

## Objective

为计划申请港新英一年制授课型硕士的中国学生/家长，提供**100% 来自官方来源、每条推荐都可溯源**的选校定位工具。MVP 数据底座只含权威层：L0 教育部认可名单 + L1 院校官方项目要求。

## Business Value

- 中介选校定位收费 1.5-3 万元，核心壁垒是信息不对称；本工具用权威公开数据 + 结构化 + 引用溯源将其打到接近零成本
- L0 监管认可名单回答家长底线问题「这学校文凭国家认不认」——中介从不主动提供，信任价值最高
- MVP 验证「透明数据 + 规则选校」的付费意愿，为低价报告商业模式探路
- 采集管线与结构化抽取为可复用资产，后续 WP-002（案例层）与品类扩展直接复用

## Users

- 主用户：目标港新英一年制硕士的本科在读/毕业生（自助申请者）
- 次用户：为孩子决策付费的家长（关注可信度与可核验性）

## User Scenarios

| ID | Scenario | User | Expected Outcome | Priority |
|---|---|---|---|---|
| S-000 | 查询某所港/新/英院校是否被中国教育部认可 | 家长 | 命中：认可状态 + 教育部来源链接；未命中：明确「未出现在认可名单中（未收录不等于不认可）」+ 名单检索页链接 | Must |
| S-001 | 输入背景（本科院校/均分/语言/目标专业），获取选校梯度 | 学生 | 冲刺/匹配/保底三档各 ≥3 个推荐，每条带 ≥1 个官方来源引用 | Must |
| S-002 | 点击推荐依据，核验原始来源（官网要求页） | 学生/家长 | 来源可访问（不可达时回落本地快照）且内容一致 | Must |
| S-003 | 输入背景明显不足或目标方向无数据 | 学生 | 明确「数据不足/背景差距过大」说明，零编造推荐 | Must |
| S-004 | 浏览项目详情（学费/要求/截止日期） | 学生 | 字段完整、标注采集时间与来源（录取背景分布延后） | Should |
| S-005 | ~~导出报告~~（延后至后续工作包） | 学生 | — | Deferred |

## Scope

### In Scope

- **L0 监管层**：教育部教育涉外监管信息网——港/新/英地区中国教育部认可院校名单，每校标注认可状态 + 来源
- **L1 院校官方层**：港三（HKU/CUHK/HKUST）+ 新二（NUS/NTU）+ 英国 G5/王爱曼华 一年制授课型硕士，覆盖**商科、计算机/数据科学**方向，≥60 个项目
- 规则选校引擎（纯确定性规则，硬性要求过滤 + margin 分档）
- 本地 Web UI + Cloudflare Tunnel 公网验证访问
- LLM 仅用于非结构化文本 → 结构化字段抽取（OpenAI 兼容可配置客户端）

### Out of Scope（CR-001 后）

- **L3 录取案例层 → WP-002**（含案例采集/向量化/相似度纠偏）
- L2 各国官方统计层 → 后续工作包
- 美加澳欧其他地区；本科/博士/MBA
- 文书、网申、签证等履约服务；账号体系、付费功能
- Workers/D1 云原生迁移（产品化阶段再议）

## Requirements

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| REQ-001 | L1 项目库：≥60 个项目，含学校/专业/学位/学制/学费/分档均分要求/院校 list/语言要求/多轮截止日期/来源/快照 | Must | 项目数 ≥60；关键字段完整率 ≥95% |
| REQ-002 | L0 认可名单库：港/新/英地区教育部认可院校全覆盖（正面清单，只存认可记录），每校含认可状态 + 官方来源 URL | Must | 覆盖率 100%（独立分母核对，见 THR-DATA-0）；与 L1 项目库按学校关联；**未命中查询按冻结契约应答「未收录≠不认可」** |
| REQ-003 | 选校梯度输出：输入背景 → 冲刺/匹配/保底各 ≥3 推荐；分档由冻结的确定性规则产生 | Must | 预声明用例集端到端成功率 100%；专家盲评合格率 ≥70% |
| REQ-004 | 引用溯源：每条推荐 ≥1 官方来源；URL 不可达回落快照 | Must | 引用覆盖率 100%；抽样 30 条人工核验一致率 ≥95%；URL 可访问率 ≥90% 且不可达者快照 100% 可用 |
| REQ-005 | 数据不足拒绝：背景不足或无数据时明确说明，零推荐 | Must | 拒绝用例集正确拒绝率 100% |
| REQ-006 | Web UI：院校认可查询 + 背景输入 + 梯度清单 + 引用跳转 | Must | 步骤化人工核验清单由非执行角色逐项签字（含免责 notice 可见断言） |
| REQ-007 | 采集幂等：重复运行不产生重复记录 | Must | 双跑行数增量 0（自然键 upsert） |
| REQ-008 | 匹配引擎零 LLM 调用 | Must | 冻结三式静态审计全部零命中 |
| REQ-009 | LLM 客户端 OpenAI 兼容可配置：base_url/api_key/model 环境变量注入，不绑定供应商 | Must | 两个不同供应商端点冒烟测试通过（配置切换零代码改动） |
| REQ-010 | 公网验证访问：cloudflared 隧道暴露本地服务为 HTTPS 公网链接 | Should | 隧道启动后外网可完成 S-001 全流程；隧道中断不影响本地功能 |

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| 官网反爬/结构变更导致采集中断 | 项目库不完整 | 种子 URL 人工维护 + 失败隔离 + 重试 |
| LLM 抽取错误污染数据 | 推荐失真 | 数字字段规则校验 + 抽样人工核验门（programs 30，字段级 ≥95%） |
| 推荐错误误导用户重大决策 | 信任崩塌/责任风险 | 全链路引用溯源（含快照回落）+ 显著免责提示 + 拒绝机制 |
| 抓取合规风险 | 法律/封禁 | 仅公开页面 + 限速 ≥1s + 遵守 robots + 非商业验证阶段 |
| Cloudflare 隧道大陆访问不稳定 | 验证用户打不开 | 验证前实测；失败则切换国内内网穿透或本地演示；隧道仅用于验证期非生产承诺 |
| 无案例纠偏导致分档偏机械 | 推荐精度受限 | 分档规则冻结且专家盲评把关；UI 标注「案例数据建设中」；WP-002 补齐 |

## Assumptions and Alternatives

| ID | Assumption/Decision | Evidence | Alternative | Falsification/Stop Condition |
|---|---|---|---|---|
| A-001 | 港新英项目硬性要求在官网公开可采 | 人工抽查 HKU/NUS/UCL 项目页均可见 | 缩范围 | D 阶段停止条件：60 项目中 >30% 无法采到要求 → 立即回 P（与 THR-SEED 兼容：THR-SEED 管单校对账，A-001 管全局可行性，任一触发即停） |
| A-003 | 规则匹配即可给出可用梯度（无案例纠偏也可接受） | 中介选校逻辑本质是硬约束过滤；案例纠偏为增强非必需 | WP-002 提前 | 专家盲评合格率 <70% → 回 P |
| A-004 | 本地 SQLite 足够 MVP | report-rag 同栈已验证 | PostgreSQL | 数据量超阈值再迁移 |
| A-005 | cloudflared 隧道满足验证期公网访问 | Cloudflare 免费隧道提供 HTTPS 公网 URL | 国内穿透服务 / 本地演示 | 目标用户实测不可访问 → 切换方案，不阻断本地交付 |

## Risk Route

- Risk assessment path: `.prdca/evidence/risk-assessment.wp-001.json`（CR-001 后于 2026-10-02 重跑 route，证据与结论一致）
- Tier: L2（route 工具输出，score 20）
- Required independent review slots: 1（route 工具裁定；评审槽位由 route 决定，非手工缩减）
- Human signoff required: Yes（PRD 在 route 输出基础上加严：推荐内容涉及用户重大决策）
- External data permitted: Yes（公开网页，限速合规）
- External AI review allowed: No（prdca.json policy）

## Evidence Pack

- Delivery ID: WP-001
- Delivery Evidence Pack path: `.prdca/evidence/delivery-evidence-pack.wp-001.json`
- Predeclared acceptance tests: E 用例集在 C 阶段前冻结于 `tests/fixtures/`

## Open Questions

- ~~「本科院校层次」分档口径~~ 已关闭（技术方案 Data Plan 已冻结枚举与判定依据）
- 教育部涉外监管网港/新/英名单页面结构与可采集性 → D 阶段第一个采集任务验证

## 范围声明（历次修订）

- S-004「往年录取背景分布」移出 WP-001（依赖案例层，随 WP-002）
- S-005 导出报告延后至后续工作包
- CR-001：L3 案例层移出至 WP-002；L0 监管层加入

## P Gate Readiness

- [x] Scope clear
- [x] Non-goals clear
- [x] Acceptance criteria measurable
- [x] Reviewers identified
- [x] Risk route recorded
- [x] Must requirements have predeclared acceptance tests
- [x] Delivery Evidence Pack initialized
