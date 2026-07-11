# TIF 工作台架构整理第三轮 Stage 2 正式复核记录

日期：2026-07-10

状态：`accepted`

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 研究工作流

打开/刷新项目 → 选择 specimen、part 或 reslice → 切换前处理未保存编辑 → 广播统一目标快照 → 加载目标 → 广播最终 Selection state；关闭项目时先阻止后台写任务，再取消并等待只读 preview，等待自动保存，处理未保存询问，最后释放 renderer/memmap 和清空界面。

## 唯一状态所有者

`TifSelectionController.state` 现在是 `specimen_id / volume_scope / part_id / reslice_id` 的唯一可写存储。Widget 的四个同名入口是兼容属性，读写直接落到 Selection state，`widget.__dict__` 不再保留副本；Shell 也不再初始化这四个字段。

## 事件与刷新顺序

- 树信号直接进入 `TifSelectionWorkflowController`，重复 bind 幂等。
- `on_selection_changing` 收到规范化目标快照。
- 加载 specimen/part/reslice 后同步 label role/display mode。
- `on_selection_changed` 广播最终 Selection state，各 controller 得到同一 context。
- 未保存询问取消时恢复旧树项，不广播 changed。
- 用户切换时的 3D pending 提示直接调用 Volume controller。

## 生命周期与旧任务

- 关闭前拒绝 import、reslice export、backend write、annotation save/truth promotion、ROI confirm 和 materialize 等后台写任务。
- Volume preview 与 Part Mask preview 在清空项目状态前 cancel/quit/wait，避免回调写已销毁界面。
- Part Mask preview 的 stale context 继续比较 specimen/scope/part/reslice。
- renderer/memmap 在项目清理阶段释放，资源问题不误报数据损坏。

## 指标

| 指标 | Stage 1 | Stage 2 |
| --- | ---: | ---: |
| 主文件物理行数 | 8,566 | 8,598 |
| Widget 方法数 | 416 | 424 |
| 4 行以内方法 | 150 | 158 |
| 主文件 `.connect(...)` | 114 | 114 |

行数和薄方法短期增加来自四个兼容属性的显式 getter/setter。它们不保存副本，Stage 9 可改用统一 descriptor 收束；当前优先证明唯一状态所有权。

## 自动门

- Selection/Lifecycle/Part Mask controller 窄测试：13 条通过。
- `tif_core` 82、`tif_storage_safety` 16、`tif_services` 24、`tif_preview_export` 106。
- `tif_workbench`：248 条通过。
- `tif_layout` 5、`tif_architecture_round3` 2、`gui_smoke` 94、`ui_polish` 83 全部通过。
- `py_compile` 和 `git diff --check` 通过（仅 LF/CRLF 提示）。

## 研究门

自动测试覆盖连续选择、stale preview、未保存取消和关闭顺序。仓库无真实 TIF fixture，真实 specimen/part/reslice 快速切换和保存重开恢复留到 Stage 10 明确人工验收，不伪造结果。

## 对照需求文档

- Selection/Lifecycle 已成为唯一上下文入口，符合要求。
- 旧任务使用统一 task context，不会把结果应用到新选择。
- 关闭顺序明确，preview 与写任务分开处理。
- 未修改项目格式、训练算法或研究数据角色。
- 仍保留 `current_part` 作为已加载记录缓存，它不是 Selection ID 副本；Stage 9 再审查是否需要独立 loaded-context model。

## 阶段结论

Stage 2 自动门和需求方向复核通过，记为 `accepted`，进入 Stage 3：Annotation、Save 与 Manual Truth。
