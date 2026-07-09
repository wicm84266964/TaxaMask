# TIF 工作台架构整理公开计划

## 背景

TIF/CT 工作台支撑 TaxaMask 的内部形态研究流程：TIF/AMIRA 导入、specimen/part/reslice 选择、ROI、mask、volume label、训练预测、3D preview、Local Axis Reslice 和结果复核。

随着功能增加，主工作台文件曾承担过 UI 构建、状态管理、后台任务、数据写入、训练预测入口、3D 预览和研究数据安全规则。长期继续堆叠会带来维护风险：

- 一个小 UI 改动可能影响保存、预览、训练或后台任务。
- 业务规则绑定 PySide 控件，难以单独测试。
- 状态分散，旧后台任务回调可能刷新错误 specimen / part / reslice。
- 安全规则散落在不同按钮处理函数里，新增入口容易绕过。

本轮架构整理的目标不是改变研究者日常操作，而是降低后续功能扩展时的连锁故障风险。

## 总目标

将 TIF 工作台从“巨型 GUI 工作台文件”整理为更可维护的分层结构：

- UI 层：显示、用户输入、按钮状态和结果呈现。
- Service / controller 层：组织完整研究动作。
- Core / domain 层：保存稳定业务规则和研究数据安全边界。
- Task 层：统一后台任务生命周期。
- Storage / project 层：管理 SQLite、manifest、sidecar 和输出目录。

## 必须保护的研究流程

1. TIF / AMIRA 导入。
2. Specimen、part 和 reslice 选择。
3. ROI 草稿、ROI 确认和 part volume 创建。
4. mask keyframe、mask preview、接受和编辑。
5. `working_edit` / `editable_ai_result` 保存。
6. `manual_truth` 生成和保护。
7. 训练数据准备、训练、预测和预测结果导入。
8. 预测结果复核、批量接受和结果对比。
9. 3D volume preview、ROI preview、mask preview 和资源不足提示。
10. Local Axis Reslice 和训练素材导出。
11. Ask Agent / AntCode 上下文同步。

## 非目标

本轮不主动做：

- 修改 TIF 项目数据格式。
- 修改 SQLite manifest / sidecar 存储语义。
- 改写 3D renderer。
- 改变训练后端契约。
- 自动迁移或修复用户研究数据。
- 宣称完成跨类群 TIF/CT 广泛验证。

数据治理、完整项目备份、只读 health check 应作为后续独立阶段推进。

## 阶段计划

### 阶段 1：低耦合结构拆分

目标：先移动低风险模块，保持行为不变。

内容：

- 翻译表和 `tt()`。
- 材料、part 命名、训练结果等 dialog。
- 2D slice canvas 和 3D volume canvas。
- Qt worker 类。
- ROI/mask 纯辅助函数。
- style、layout、page 和 control panel 组合逻辑。

验收：

- 工作台能正常导入和实例化。
- 旧测试导入路径仍可用。
- 按钮、弹窗、canvas、worker 信号行为不变。

### 阶段 2：核心安全规则下沉

目标：把研究数据安全规则集中到 core/policy 层。

内容：

- label role 写入矩阵。
- truth promotion policy。
- prediction import policy。
- write intent guard。
- source stack overwrite guard。

验收：

- `manual_truth` 不被预测或草稿自动覆盖。
- `raw_ai_prediction_backup` 保持只读审计语义。
- 预测导入进入可复核层。
- 路径写入有项目边界检查。

### 阶段 3：Service / controller 化

目标：把完整研究动作从 Widget 方法中抽出。

内容：

- selection state。
- label edit request。
- truth promotion。
- ROI part request。
- backend workflow selection。
- volume preview request。
- Local Axis draft/frame/reslice payload。

验收：

- service/controller 有 GUI 无关测试。
- UI 主要负责收集输入和展示结果。
- 新增后端或批处理时可以复用 service/core。

### 阶段 4：统一 task/state

目标：降低后台任务生命周期混乱和旧回调污染风险。

内容：

- task context。
- task state。
- task manager。
- busy lock。
- selection/edit/preview/backend/ROI/local-axis 状态摘要。

验收：

- 旧任务完成后不会刷新错误对象。
- 保存、训练、预测、预览、Local Axis export 的运行状态可查询。
- Ask Agent 能看到当前 task/state summary。

### 阶段 5：页面与高风险 UI 控制器

目标：继续瘦身主 Widget，控制 UI 页面复杂度。

内容：

- layout/page/control panel 拆分。
- Training / prediction panel controller。
- Preview / resource controller。
- Local Axis UI controller。
- Agent context builder。

验收：

- 右侧栏滚动和页面栈正常。
- 按钮中文和 objectName 稳定。
- Local Axis 三点链路可用。
- 训练/预测入口仍调用既有 guard。

### 阶段 6：测试分层和候选版本收口

目标：让后续维护可以快速定位问题。

测试分层：

- core safety。
- storage safety。
- service/task。
- preview/export。
- model backend。
- workbench GUI key paths。
- smoke / polish。
- Agent context。

候选版本必须记录：

- 自动测试摘要。
- 人工验收缺口。
- 未改变的数据边界。
- 后续数据治理计划。

## 执行注意事项

- GUI 测试必须使用带 PySide6 的 TaxaMask 运行环境；如果测试因为缺少 PySide6 被 skip，不能视为通过。
- 每次移动 UI 控件后，要检查右侧栏滚动、中文文案、objectName 和按钮状态。
- 每次触碰 preview busy lock 或 task lock 后，要人工复核 Local Axis 三点选择。
- 每次触碰 Agent context 后，要检查生成字段、压缩字段和面板提示是否一致。
- 资源不足、页面文件不足或后台训练占用显存时，应先区分环境压力和代码回归。
- 提交前必须确认没有数据库、TIF/CT stack、模型权重、run outputs、API 配置或本地项目 JSON 进入 Git。

## 完成判断

本轮架构整理完成后应满足：

- TIF 工作台主 Widget 职责密度下降。
- 新业务规则优先进入 core/service/task 层。
- 研究数据安全 guard 更集中。
- 后台任务有统一状态。
- Agent 能读取当前 TIF 现场摘要。
- 自动测试覆盖主要安全边界。
- 真实 TIF/GPU 人工验收没有阻断问题。
