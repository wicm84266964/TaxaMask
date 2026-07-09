# TIF 工作台架构整理验证摘要

## 范围

本文总结 TIF/CT 工作台架构整理的公开验证结果。它替代内部 Stage 复核日志，用于说明本轮重构覆盖了哪些方向、哪些自动化测试已执行，以及发布前真实项目人工验收结论。

本轮目标是改善架构可维护性，而不是改变 TIF 项目数据格式、训练后端语义或 `manual_truth` 安全边界。

## 主要完成项

### UI 结构拆分

- 翻译、弹窗、canvas、worker、helper、style、layout/page/control panel 等从主工作台中拆出。
- 保留 `TifWorkbenchWidget` 作为外部入口。
- 保留关键 objectName，减少 GUI smoke 和用户习惯断裂。

### Service / controller

- Selection、label edit、truth promotion、ROI part、backend workflow、volume preview、Local Axis 等职责进入 service/controller。
- UI 仍负责展示和用户交互，核心规则优先由 service/core 判断。

### Task / state

- 新增或整理 task context/state/manager。
- TIF import、materialize、save、truth promotion、ROI、backend、preview、Local Axis export 等链路进入统一 task 生命周期。
- 工作台可以生成 selection/edit/preview/backend/ROI/local-axis 状态摘要。

### 资源不足处理

- 预览资源异常被分类为更可理解的状态。
- 系统内存、提交内存、GPU/OpenGL、volume IO 失败应尽量提示用户，而不是直接让研究者误判为数据损坏。

### Agent context

- Ask Agent 上下文包含 TIF task/state summary、当前 specimen/part/reslice、训练预测摘要、preview/resource、Local Axis 状态和相关源码引用。
- 主窗口压缩上下文和 Agent 面板展示已补齐这些字段。

## 自动化验证范围

验证覆盖以下类型：

- TIF core safety。
- TIF storage / write guard。
- TIF service / task。
- Preview / export。
- TIF model backends。
- TIF workbench GUI key paths。
- GUI smoke。
- UI polish。
- Layout。
- PDF safety。
- Validation tooling。
- SQLite migration。
- Agent context routes。
- Blink / locator。
- PDF literature。
- Generic VLM / STL。

这些测试主要验证：

- 数据安全 guard 不被绕过。
- service/controller 契约稳定。
- 关键 GUI 控件和对象名存在。
- 训练/预测入口和预测导入边界保持正确。
- Agent context 不丢失关键 TIF 状态。

## 发布前人工验收结果

自动化测试不能完全替代真实 TIF/GPU 验收。本版本发布前已使用真实 TIF 项目完成基础人工检查，未发现阻断发布的问题。人工确认覆盖：

1. 打开真实 TIF 项目。
2. 切换 specimen、part、reslice。
3. 查看切片和标签层。
4. 保存 working edit 并重开确认。
5. 打开 3D volume preview。
6. 检查 mask / boundary / masked image 显示。
7. 走完整 Local Axis 三点参考、对齐、重切片、保存重开链路。
8. 检查训练/预测入口、预测分组和目标选择。
9. 导入预测结果，确认进入 editable AI result / review draft，而不是直接覆盖 `manual_truth`。
10. 在资源紧张时确认提示可理解，项目数据未被修改。

## 已知边界

本轮没有宣称：

- 完成完整数据治理。
- 完成项目打包备份。
- 完成只读 health check。
- 重写 3D renderer。
- 改变 SQLite / sidecar 语义。
- 让 TIF/CT 支持范围扩展到所有类群并完成验证。

这些方向适合后续单独开分支推进，第一版宜从只读检查和备份开始。

## 发布判断

本轮已通过自动化验证和真实项目人工验收，可以作为 TaxaMask 2.3.0 发布。

后续在更多机器、更大体积 TIF/CT stack 和不同显卡环境中使用时，应继续把以下问题作为回归检查重点：

- 程序崩溃。
- 保存丢失或打开失败。
- `manual_truth` 被自动覆盖。
- Local Axis 三点或导出不可用。
- 预测导入写错层。
- 旧后台任务刷新到错误 specimen / part / reslice。

非阻断问题包括：

- 文案轻微不顺。
- 个别按钮提示需要优化。
- 3D 预览视觉参数需要继续调优。
- 某些极端大 TIF 在资源不足时需要降低质量或稍后重试。
