# TIF 工作台架构整理第三轮 Stage 3 正式复核记录

日期：2026-07-10

状态：`accepted`

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 研究工作流

加载 working edit / editable AI result → 选择工具 → Canvas 编辑 → 记录 slice revision 与 dirty → 自动或手动保存快照 → 仅清除相同 revision → 失败保留 dirty → 经 truth promotion service 提升 manual truth。

## 唯一状态与 worker 所有者

- dirty slices、slice revisions、revision counter、tool、undo/redo、stroke 状态只存于 `TifAnnotationWorkflowController.state`。
- auto-save/manual-save/promotion thread、worker、token、task id 和 pending request 只存于 Annotation controller。
- Widget 旧名称是直接属性视图，Shell 不再初始化副本；`_sync_mirror` 不再写 Widget。
- `_pending_backend_action_after_save` 属于跨工作流协调，留到 Stage 9 coordinator。

## 信号与兼容入口

- 26 条工具、保存、自动保存、promotion、插值和快捷键信号由 Annotation controller 幂等注册。
- 插值按钮不再经过 Widget wrapper。
- Canvas 编辑入口暂作为稳定 view contract 保留，实际立即调用 Annotation controller；Stage 9 再审查是否改为 Canvas 直接引用 controller。
- 同步 `save_working_edit` 因现有 GUI/外部调用保留为明确公开兼容入口；按钮、快捷键和后台保存均不经过它，Stage 9 按调用表决定退场。
- 三个无调用 promotion 私有 wrapper 已删除。

## 数据安全

- 自动保存按 slice revision 清理，后来同切片编辑不会被旧完成回调清除。
- 保存失败保持 dirty 并可重试。
- raw prediction 角色不可写、不可直接提升 manual truth。
- promotion controller 不直接写 manual truth，只调用 truth promotion service/core guard。

## 指标

| 指标 | Stage 2 | Stage 3 |
| --- | ---: | ---: |
| 主文件物理行数 | 8,598 | 8,817 |
| Widget 方法数 | 424 | 478 |
| 4 行以内方法 | 158 | 212 |
| 主文件 `.connect(...)` | 114 | 113 |

显式兼容属性使行数/方法数暂增，但消除了重复存储。Stage 9 必须将这些同构属性改为统一 descriptor，使最终方法数和行数达到目标。

## 自动门

- Annotation/service/truth safety 窄测试：12 条通过。
- `tif_core` 82、`tif_storage_safety` 16、`tif_services` 24、`tif_preview_export` 106。
- `tif_workbench` 249、`tif_layout` 5、`tif_architecture_round3` 2、`gui_smoke` 94、`ui_polish` 83 全部通过。
- `py_compile` 与 `git diff --check` 通过（仅 LF/CRLF 提示）。

## 研究门

自动测试覆盖多切片 dirty、同切片并发编辑、手动保存、失败恢复、promotion guard 和关闭/训练前提示。真实 TIF 手工保存重开与 manual truth 核对留到 Stage 10，不伪造结果。

## 对照需求文档

状态、信号、worker、直接测试和数据角色 guard 已同步迁移；未复制安全规则，未修改数据格式或训练算法。方向符合要求。

## 阶段结论

Stage 3 通过并记为 `accepted`，进入 Stage 4：ROI-to-Part。
