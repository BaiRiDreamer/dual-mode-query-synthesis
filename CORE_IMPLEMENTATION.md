# 双模式查询合成 - 核心实现方案

## 核心实现架构

### 1. 多阶段处理流水线

采用 **六阶段流水线** + **双模式并行构建** 的混合策略：

```
数据加载 → 上下文增强 → 意图合成 → 查询构建 → 真值生成 → 提示渲染
```

### 2. 关键技术决策

| 维度 | 方案 | 理由 |
|------|------|------|
| 语义理解 | LLM (Azure OpenAI) | 可选增强意图合成，超越规则提取 |
| 数据获取 | GitHub API + 缓存 | 智能缓存减少 80%+ API 调用 |
| 并发处理 | ThreadPoolExecutor | 5-10x 性能提升，充分利用 I/O 等待 |
| 模板系统 | Jinja2 | 灵活定制，分离逻辑与表现 |
| 真值生成 | 双层补丁 | 链级累积 + 原子级独立 |

---

## 技术架构

### 数据流

```
输入: PR-list-output.jsonl (已筛选的 PR 链)
  ↓
[阶段 1] 数据加载与过滤
  - 加载 JSONL 格式的 PR 链
  - 过滤: status="approved", quality_score >= 8.0
  ↓
[阶段 2] 上下文增强 (GitHub API)
  - 并发获取 PR 详情 (title, body, author, dates)
  - 获取文件变更列表
  - 获取代码补丁 (diff patches)
  - 智能缓存 (.cache/github/)
  ↓
[阶段 3] 意图合成
  - 提取主题和演化模式
  - 合成高级意图 (链级/原子级)
  - 构建演化叙事
  - 可选: LLM 增强
  ↓
[阶段 4] 查询构建 (双模式)
  ├─ 链级构建器
  │   - 整体演化建模
  │   - 跨 PR 依赖跟踪
  │   - PR 序列角色分配
  └─ 原子级构建器
      - 独立 PR 查询
      - 链上下文感知
      - 聚焦任务规范
  ↓
[阶段 5] 真值生成
  - 链级: 累积补丁 (所有 PR)
  - 原子级: 单个 PR 补丁
  - 验证标准生成
  ↓
[阶段 6] 提示渲染 (Jinja2)
  - 基于模板渲染最终提示
  - 注入元数据和上下文
  ↓
输出:
  - data/output/chain/*.jsonl (链级查询)
  - data/output/atomic/*.jsonl (原子级查询)
```

---

## 实现细节

### 1. 数据加载与过滤

**文件**: `src/cli/dual_mode_query_constructor_cli.py`

```python
# 加载配置
config = load_config("config/config.yaml")

# 加载 PR 链
chains = load_chains(input_path)

# 过滤逻辑
def filter_chains(chains, approved_only=True, min_quality_score=8.0):
    filtered = []
    for chain in chains:
        # 状态过滤
        if approved_only and chain.get("status") != "approved":
            continue

        # 质量分数过滤
        if chain.get("quality_score", 0) < min_quality_score:
            continue

        # PR 数量过滤 (2-10 个)
        if not (2 <= len(chain.get("original_chain", [])) <= 10):
            continue

        filtered.append(chain)

    return filtered
```

**输入格式**:
```json
{
  "chain_id": "chain_0001",
  "original_chain": ["scipy/scipy#333", "scipy/scipy#334"],
  "status": "approved",
  "quality_score": 9.0,
  "file_overlap_rate": 0.65,
  "llm_judgment": {
    "reasoning": "Both PRs focus on scipy.special refactoring",
    "evolution_pattern": "incremental_enhancement",
    "function_types": ["MAINT", "ENH"]
  }
}
```

---

### 2. 上下文增强 (GitHub API)

**文件**: `src/pipelines/query_constructor/context_enricher.py`

**核心功能**:
