# Agent Center 集成设计

## 定位

TaxaMask 内嵌 Agent Center，用于帮助研究者理解当前工作台状态、排查错误、审查配置，并在用户确认后修改本地代码。它不是云端数据上传通道，也不应默认读取完整私有项目数据。

Agent Center 的价值在于：TaxaMask 功能复杂，研究者遇到 PDF、2D/STL、TIF、训练预测或配置问题时，可以让本地 Agent 基于当前源码和压缩上下文辅助判断。

## 上下文原则

Ask Agent 传递的是紧凑上下文，而不是完整项目数据。

上下文应包含：

- 当前工作台来源。
- 当前项目类型。
- 当前选择摘要。
- 当前运行状态。
- 相关源码或契约位置。
- 安全边界提示。
- 最近少量日志。

上下文不应默认包含：

- API key。
- 私有网关地址。
- 完整数据库内容。
- 大型 TIF sidecar。
- 全量 PDF 文本。
- 完整运行日志。

## 路由

Agent context route 根据 `source_workbench` 或 settings scope 判断当前问题属于：

- general settings。
- 2D/STL model settings。
- TIF backend settings。
- 2D/STL labeling workbench。
- Blink refinement。
- TIF volume workbench。
- PDF evidence。

每条 route 应提供：

- diagnostic route。
- diagnostic focus。
- source code references。
- artifact hints。
- safety notes。
- suggested next action。

## TIF 上下文

TIF 工作台上下文尤其需要包含：

- specimen / part / reslice。
- label role 和 label schema。
- train-ready 样本数量。
- backend run 状态。
- selected model manifest。
- predict group 和 targets。
- preview / GPU / resource 状态。
- Local Axis 状态。
- task/state summary。

这样 Agent 才能判断问题是在保存、训练、预测、预览、资源不足、Local Axis 还是数据安全边界。

## 安全边界

Agent 可以建议、解释和修改代码，但高风险动作必须经过用户确认：

- 删除项目文件。
- 覆盖 `manual_truth`。
- 清理运行目录。
- 启动 GPU/训练重任务。
- 修改长期配置。
- 发布或推送代码。

如果源程序无法启动，Agent Center 的恢复入口仍可作为本地修复面板使用。

## 文档边界

公开文档只描述 Agent Center 的架构和安全原则，不公开本地工作区路径、个人配置、私有模型网关或一次性调试记录。
