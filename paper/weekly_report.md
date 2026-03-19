# 周进度报告

**项目名称**：AI Expert Consultation Platform（集体AI审议框架）
**报告周期**：2026年3月第2周
**报告人**：Andrew

---

## 一、本周概要

本周完成了项目从"预测市场辩论器"到"AI专家咨询平台"的方向确认与核心转型，交付了可运行的MVP Demo及配套白皮书。

---

## 二、已完成工作

### 1. 项目方向确认

- **定位转型**：从原有的"AI辩手自动辩论输出概率"模式，转型为"用户带着观点与AI专家团互动、修正认知、获得结构化建议"的专家咨询模式
- **核心差异**：用户从旁观者变为参与者，输出从单一概率值变为结构化咨询报告
- **目标场景**：首批聚焦加密货币（Crypto）和体育竞技（Sports）两个垂直领域

### 2. MVP Demo 开发完成

#### 2.1 核心代码（6个新增文件）

| 文件 | 功能 | 状态 |
|------|------|------|
| `expert_panels.py` | Crypto（5专家）+ Sports（5专家）领域定义 | 已完成 |
| `consult_agent.py` | 咨询专家Agent，支持4阶段交互 | 已完成 |
| `consultation.py` | 咨询流程编排器，并行执行 | 已完成 |
| `knowledge_loader.py` | Level 2 知识档案加载与克隆提示词构建 | 已完成 |
| `app_consult.py` | Streamlit交互式前端 | 已完成 |
| `convert_pdf.py` | 白皮书PDF转换工具 | 已完成 |

#### 2.2 Level 2 AI克隆体系（10份知识档案）

为每位专家编写了完整的知识档案（分析框架 + 3个少样本示例 + 典型表达风格），共计约52KB：

**Crypto领域：**
- 链上数据分析师（原型：Willy Woo / Glassnode）
- 宏观经济学家（原型：Raoul Pal / Lyn Alden）
- 加密原生研究员（原型：Arthur Hayes / Messari）
- 风险管理顾问（原型：Nassim Taleb / Kelly准则）
- 监管政策专家（原型：a16z Policy / Coin Center）

**Sports领域：**
- 数据统计专家（原型：FiveThirtyEight / Nate Silver）
- 战术分析师（原型：Zach Lowe / Zonal Marking）
- 伤病体能专家（原型：运动医学视角）
- 博彩市场分析师（原型：Pinnacle / Sharp市场理论）
- 资深体育评论员（原型：Bill Simmons）

#### 2.3 Prompt模板（5个新增）

- `consult_system.txt` — 专家系统人设
- `consult_evaluate.txt` — Phase 1：独立评估
- `consult_respond.txt` — Phase 2：与用户对话
- `consult_discuss.txt` — Phase 3：专家圆桌讨论
- `consult_final.txt` — Phase 4：最终建议

#### 2.4 产品流程

```
用户输入（话题 + 观点）
    ↓
Phase 1：5位专家独立评估用户观点（并行，约30秒）
    ↓
Phase 2：用户与任意专家一对一聊天（交互式）
    ↓
Phase 3：专家之间互相讨论（并行，约30秒）
    ↓
Phase 4：每位专家给出最终评估与建议（并行，约30秒）
    ↓
结构化报告：置信度变化图表 + 关键洞察 + 盲点 + 建议 + 风险警示
```

### 3. 白皮书撰写完成

- **标题**：《集体AI审议：基于多专家咨询的人类观点精炼框架》
- **内容**：约5,000词，包含11个章节 + 3个附录
- **核心论点**：通过多专家结构化认知冲突克服单一LLM的迎合性问题
- **版本**：中英文双语版本均已完成
- **文件路径**：`paper/whitepaper.md`（英文）、`paper/whitepaper_cn.md`（中文）

白皮书涵盖：
- 问题定义与动机
- Level 2 AI克隆方法论
- 4阶段咨询流程设计
- 信息检索与知识锚定
- 技术实现细节
- Crypto + Sports两个应用案例
- 评估框架设计
- 局限性与未来方向
- API成本分析（约$0.02/次咨询）

---

## 三、关键技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 克隆层级 | Level 2（知识档案注入） | 平衡效果与成本，无需微调 |
| 专家数量 | 每领域5人 | 覆盖主要视角，成本可控 |
| 交互模式 | 4阶段流程 | 兼顾独立性（防群体思维）和交互性（用户参与） |
| LLM后端 | DeepSeek V3为主 | 成本最优，约$0.02/次完整咨询 |
| 前端框架 | Streamlit | 快速原型，适合Demo阶段 |

---

## 四、下周计划

### P0 — Level 3 克隆体系实现
- [ ] 收集专家语料数据（Arthur Hayes博客、Willy Woo推文、Nate Silver分析等公开文本）
- [ ] 语料清洗与训练对构建（问题-专家风格回答 对）
- [ ] 基于开源基座模型（LLaMA/Qwen）完成LoRA微调，产出专家适配器
- [ ] 实现Level 3推理接口，与现有ConsultAgent兼容
- [ ] 完成三级克隆结构闭环：Level 1（纯人设）→ Level 2（知识档案）→ Level 3（LoRA微调）

### P1 — 产品完善
- [ ] 修复PDF中文字体渲染问题
- [ ] 增加咨询历史记录与回看功能
- [ ] 优化Phase 2聊天体验（流式输出）
- [ ] 优化Phase 2交互和网站上线


### P2 — 评估实验
- [ ] 构建50题评估数据集（25 Crypto + 25 Sports）
- [ ] 实现自动化评估脚本（Brier Score对比）
- [ ] 跑Level 1 vs Level 2 vs Level 3 三级对比实验，量化各层级克隆的提升效果


