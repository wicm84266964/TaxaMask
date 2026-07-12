# TaxaMask 公开架构与设计文档

本目录保存整理后的公开架构文档。它们来自 TaxaMask 长期设计稿、TIF/CT 工作台实施记录、PDF evidence 路线、Blink/模型路由讨论和 Agent Center 集成经验，但已经去除了本地路径、临时交接语气和施工流水账。

这些文档的目标不是替代用户手册，而是帮助开发者、研究合作者和高级用户理解 TaxaMask 为什么这样设计，以及哪些研究数据边界不能被绕过。

## 建议阅读顺序

1. `taxamask_architecture_overview_zh.md`
   - 总览 TaxaMask 的 PDF、2D/STL、TIF/CT 和 Agent Center 四条主要路线。

2. `taxamask_refactor_round3_round4_summary_zh.md`
   - 汇总第三轮 TIF 工作台与第四轮主窗口优化的设计边界、量化结果、性能和验收结论。

3. `data_safety_and_truth_policy_zh.md`
   - 说明人工真值、AI 草稿、PDF evidence、TIF prediction draft 和训练样本之间的安全边界。

4. `tif_ct_workbench_architecture_zh.md`
   - 说明 TIF/CT 工作台的数据结构、sidecar、SQLite manifest、训练预测和 3D 预览架构。

5. `local_axis_reslice_design_zh.md`
   - 说明 Local Axis Reslice 的目标、局部坐标系、AI proposal 边界和重切片保存原则。

6. `blink_and_model_routing_design_zh.md`
   - 说明 2D/STL 路线中的 Locator/SAM、Blink、小部位专家和模型路由治理。

7. `pdf_evidence_workflow_design_zh.md`
   - 说明 PDF 文献证据路线如何提供候选材料和 provenance，而不直接污染训练真值。

8. `agent_center_integration_zh.md`
   - 说明内嵌 Agent Center / Ant-Code 的上下文边界、Ask Agent 路由和安全限制。

9. `design_history_index_zh.md`
   - 用公开摘要的方式整理历史设计主题，而不是公开原始施工日志。

## 文档边界

本目录不包含：

- 私有研究数据、TIF/CT stack、PDF 原文、数据库、模型权重或运行输出。
- 本地 API key、网关地址、用户配置或工作站路径。
- 临时 AI handoff、未整理的讨论记录和一次性调试日志。

如果文档与代码行为不一致，以当前代码、用户手册和 release note 为准；设计文档用于解释架构意图和后续维护方向。
