# TIF 工作台架构整理第三轮 Stage 6 正式复核记录

日期：2026-07-10

状态：`accepted`（自动门通过；真实 GPU/TIF 清晰度验收留 Stage 10）

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 研究工作流闭环

选择 3D source → 形成 owner/context cache key → drag/still preview → GPU texture 或 CPU fallback → 合成只读 overlay → 显示资源状态 → 取消或拒绝 stale result。

## 状态所有权

- `TifVolumeRenderState` 是 preview cache、render mode、交互调度、GPU/CPU 状态和 pending token 的唯一存储。
- Shell 删除 Volume 默认字段清单，不再通过兼容属性执行第二次初始化。
- `volume_interaction_render_interval_ms` 也进入 Volume state。
- Widget 的 descriptor 仅作为过渡兼容入口，Stage 9 统一收束；Widget/Shell 不保存独立副本。

## 信号合同

Volume controller 直接登记 38 条连接：display/quality/source/transfer/mask/overlay 控件、3 组交互 slider press/change/release 和 still timer。重复 bind 保持 38 条，不产生双触发。

## 后台与 renderer 安全

- stale specimen/part/reslice/display context 的结果被取消，不写 cache、不刷新新选择。
- cancel/wait 会取消 worker，并等待 thread 退出。
- GPU renderer failure 切换到 CPU canvas，再调度重绘。
- page-file、系统内存和 volume I/O 失败按 resource policy 提示；不再一律误报为“GPU 失败”，也不把资源问题说成 TIF 数据损坏。
- Renderer 数学、shader、Local Axis 数学和数据格式未修改。

## 直接测试

新增 `tests/test_tif_volume_render_controller.py`，7 条合同覆盖：

- 38 条信号与幂等 bind。
- stale context。
- GPU → CPU fallback。
- commit-memory 提示分类。
- worker/thread 取消等待。
- Shell 无 Volume state 副本。
- controller 小于 3,000 行、无重复方法、不访问其他 workflow controller 内部 state。

测试已加入标准 `tif_workbench` suite。

## 全层自动门

- `tif_core`：82
- `tif_storage_safety`：16
- `tif_services`：24
- `tif_preview_export`：106
- `tif_workbench`：265
- `tif_layout`：5
- `tif_architecture_round3`：2
- `gui_smoke`：94
- `ui_polish`：83

合计 677 条全部通过。

## 架构指标

| 指标 | Stage 5 | Stage 6 |
| --- | ---: | ---: |
| 主文件物理行数 | 8,817 | 8,818 |
| Widget 方法数 | 478 | 478 |
| 薄方法数 | 212 | 212 |
| 主文件 `.connect()` | 113 | 113 |
| Volume controller | 2,476 | 2,481 |

主文件增加 1 行来自 interval 兼容 descriptor；实际重复 Shell 状态清单被删除。Stage 6 的完成依据是状态、信号、错误分类和测试边界，不是净行数。

## 研究门与需求对照

- fake view/state 可直接测试：符合。
- still/drag、取消、stale context 无回退：符合自动合同。
- GPU 不可用时恢复 CPU：符合自动合同。
- Preview 不写其他 workflow 内部 state：符合 AST 合同。
- 资源不足与数据损坏提示分开：符合。
- 真实 GPU source/mask/ROI/Local Axis overlay 清晰度：仓库无安全 fixture，保持待 Stage 10 人工验收。

## 阶段结论

Stage 6 自动门、架构门和需求方向复核通过，记为 `accepted`，进入 Stage 7：Local Axis 与 Reslice。
