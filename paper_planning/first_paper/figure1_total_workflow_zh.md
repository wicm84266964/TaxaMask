# Figure 1 总流程图草案

## 图题建议

Figure 1. TaxaMask 第一篇验证链路：从分类学文献证据到蚂蚁形态标注训练数据集。

## 图注草案

TaxaMask 将分类学 PDF 中的图版、caption/邻近文本和部位描述整理为可追溯 evidence layer，并将文献证据支持的结构关系转化为 `parent -> child` route。经研究者确认后，route 被写入 2D/STL 标注工作台；VLM、Locator 和 SAM 负责候选起稿，Blink 作为小部位父级上下文训练策略积累 trajectory 并训练 route expert。所有 AI 输出保持为草稿，只有人工确认后的标注进入训练集导出。Ant-Code Agent Center 横跨以上阶段，读取项目状态、配置、日志、后端契约和源码线索，协助诊断与适配，但不替代人工确权。TIF/CT 体数据链路属于平台扩展，本文不评估。

## Mermaid 草图

```mermaid
flowchart LR
  classDef source fill:#eef6ff,stroke:#5b7fa6,color:#111;
  classDef evidence fill:#fff7e6,stroke:#b58a2a,color:#111;
  classDef route fill:#f1f8e9,stroke:#6a9b45,color:#111;
  classDef workbench fill:#f3fbf5,stroke:#5d996a,color:#111;
  classDef model fill:#eef5ff,stroke:#4f7fbf,color:#111;
  classDef blink fill:#f7f1ff,stroke:#7a63b8,color:#111;
  classDef review fill:#fff0f0,stroke:#b55a5a,color:#111;
  classDef output fill:#f7f7f7,stroke:#777,color:#111;
  classDef agent fill:#f3efff,stroke:#7a63b8,color:#111;
  classDef scope fill:#fafafa,stroke:#aaa,stroke-dasharray: 4 4,color:#444;

  subgraph L["文献与图像来源"]
    direction TB
    L1["分类学 PDF<br/>正文、caption、图版"]
    L2["PDF 图版裁剪图<br/>文献来源可追溯"]
    L3["普通 2D 标本图像"]
    L4["STL 渲染视图<br/>固定视角 2D 图像"]
  end

  subgraph E["PDF Evidence Layer"]
    direction TB
    E1["PDF 筛选"]
    E2["图版提取<br/>caption / 邻近文本组装"]
    E3["部位描述抽取<br/>taxon -> part -> description"]
    E4["SQLite evidence DB<br/>source / page / figure / text block"]
    E1 --> E2 --> E4
    E1 --> E3 --> E4
  end

  subgraph R["文献证据支持的性状 route"]
    direction TB
    R1["性状证据表<br/>原文描述 -> 标准化结构"]
    R2["父子 route candidates<br/>Head -> Eye<br/>Head -> Mandible<br/>Head -> Scape"]
    R3["研究者复核<br/>确认 / 修正 / 删除"]
    R4["项目 route manifest<br/>写入标注工作台"]
    R1 --> R2 --> R3 --> R4
  end

  subgraph W["2D/STL Morphology Workbench"]
    direction TB
    W1["图像导入与标本关联"]
    W2["结构标签与父级上下文<br/>Head / Mesosoma / Gaster"]
    W3["草稿标注层<br/>AI 输出不直接进入训练"]
    W4["人工确认后的 polygon / mask"]
    W1 --> W2 --> W3 --> W4
  end

  subgraph M["可替换的候选标注模型"]
    direction TB
    M1["VLM 冷启动候选框"]
    M2["Locator 主部位定位"]
    M3["SAM 提示式草稿 mask"]
    M4["外部后端契约<br/>可接入自有模型"]
  end

  subgraph B["Blink 小部位训练策略"]
    direction TB
    B1["父级框<br/>Head context"]
    B2["loose box 与人工子部位 mask"]
    B3["trajectory 积累"]
    B4["route expert 训练<br/>当前 parent -> child"]
    B5["后续小部位起稿"]
    B1 --> B2 --> B3 --> B4 --> B5
  end

  subgraph H["训练安全边界"]
    direction TB
    H1["AI 草稿<br/>draft / Auto-Annotated"]
    H2["人工确权<br/>confirmed / edited / rejected"]
    H3["训练预检<br/>跳过未复核草稿"]
    H1 --> H2 --> H3
  end

  subgraph O["训练数据与审计产物"]
    direction TB
    O1["COCO / YOLO / JSONL"]
    O2["manifest / report"]
    O3["provenance index<br/>PDF evidence -> image -> mask"]
  end

  subgraph A["Ant-Code Agent Center"]
    direction TB
    A1["读取项目状态、配置、日志"]
    A2["解释 route / 后端契约 / 运行产物"]
    A3["权限控制下协助适配模型或排查源码"]
    A1 --> A2 --> A3
  end

  X["平台扩展：TIF/CT 体数据链路<br/>代码库中存在，本文不评估"]:::scope

  L1 --> E1
  E4 --> R1
  L2 --> W1
  L3 --> W1
  L4 --> W1
  R4 --> W2

  M1 --> W3
  M2 --> W2
  M3 --> W3
  M4 -.-> M1
  M4 -.-> M2
  M4 -.-> M3

  W2 --> B1
  W4 --> B2
  B5 --> W3

  W3 --> H1
  W4 --> H2
  H3 --> O1
  E4 --> O3
  W4 --> O3
  H3 --> O2

  A1 -.-> E4
  A1 -.-> R4
  A1 -.-> W1
  A2 -.-> M4
  A2 -.-> O2
  A3 -.-> M4

  class L1,L2,L3,L4 source;
  class E1,E2,E3,E4 evidence;
  class R1,R2,R3,R4 route;
  class W1,W2,W3,W4 workbench;
  class M1,M2,M3,M4 model;
  class B1,B2,B3,B4,B5 blink;
  class H1,H2,H3 review;
  class O1,O2,O3 output;
  class A1,A2,A3 agent;
```
