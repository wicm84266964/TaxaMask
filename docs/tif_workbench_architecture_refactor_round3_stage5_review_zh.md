# TIF 工作台架构整理第三轮 Stage 5 正式复核记录

日期：2026-07-10

状态：`accepted`（自动门重新通过；真实 TIF 操作统一留 Stage 10）

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

执行清单：`docs/tif_workbench_architecture_refactor_round3_execution_checklist_zh.md`

## 研究工作流闭环

- 加载 part mask/material schema，选择、新增、编辑或删除材料。
- 在关键切片绘制 contour、复制或清除当前材料、跳转关键切片。
- 构建 mask preview，检查质量，取消、重建或接受。
- ROI controller 只通过 `load_roi_draft_keyframes()` / `clear_roi_draft_keyframes()` command 交付草稿，不写 Part Mask 内部 state。
- 接受 preview 后才写 accepted part mask；preview 本身不成为 manual truth。
- metadata-only specimen 通过后台 materialize 创建 working volume，原始 TIF 保留。

## 状态与跨工作流边界

`TifPartMaskWorkflowController` 唯一持有 draft keyframes、preview、accepted/editable mask 视图、材料状态，以及 preview/materialize worker 生命周期。Widget 不赋值这些字段。

本次严格复核额外修正 Selection → Annotation 的内部状态读取：Annotation 新增公开查询 `has_unsaved_changes()`，Selection 不再访问另一个 controller 的 `.state`。这保证跨工作流只使用 command/query，不形成新的中央耦合。

## 信号与后台任务

- 16 条材料、contour、关键切片、preview、accept、clear 信号由 Part Mask controller 直接注册。
- 重复 bind 不产生双触发。
- stale preview token/context 不覆盖较新的 preview 或新的 specimen/part/reslice。
- `cancel_and_wait_preview()` 会调用 worker cancel、thread quit/wait，并清空 worker/thread 引用。

## 数据角色与安全

- draft、preview、accepted/editable 状态分离。
- 加载或清除 ROI draft 不改 accepted mask 引用和持久化结果。
- background 0 不能删除；仍被 label volume 使用的 material 不能删除。
- accepted mask 写入继续经过既有 `write_part_mask` 和 sidecar guard。
- metadata-only materialize 建立 working volume；source TIF 在 specimen 目录内外都不会被删除。
- 未修改 manual truth、raw prediction、项目格式、训练算法或 renderer 数学。

## 自动门

本次新增/复核 21 条窄测试全部通过，其中 Part Mask controller 8 条；metadata-only materialize 两条真实临时 TIF 测试通过。

全层验证全部通过：

- `tif_core`：82
- `tif_storage_safety`：16
- `tif_services`：24
- `tif_preview_export`：106
- `tif_workbench`：250
- `tif_layout`：5
- `tif_architecture_round3`：2
- `gui_smoke`：94
- `ui_polish`：83

合计 662 条，无失败。

## 当前架构指标

| 指标 | 发布基线 | Stage 5 正式复核工作树 |
| --- | ---: | ---: |
| 主文件物理行数 | 14,234 | 8,817 |
| Widget 方法数 | 664 | 478 |
| 4 行以内薄方法 | 147 | 212 |
| 主文件 `.connect()` | 251 | 113 |
| 私有测试引用次数 | 569 | 410 |
| Part Mask controller | 0 | 1,595 |

显式兼容属性使 Widget 方法数与薄方法数暂时偏高，属于 Stage 9 必须收束的已登记债务，不能把 8,817 行单独解释为完成。

## 研究门

仓库没有可安全直接使用的真实研究项目 fixture。本阶段不伪造人工结论；真实 part mask/material preview、接受、保存和重开核对保留在 Stage 10。

## 对照需求文档

- 完整研究动作、状态、信号、worker 和测试同步迁移：符合。
- draft/preview/accepted 角色清晰：符合。
- 原始 TIF、manual truth 和 raw prediction 无回退：符合。
- controller 1,595 行，低于 3,000 行硬限制：符合。
- 真实研究流程尚未人工执行：已明确延期到 Stage 10，不冒充完成。

## 阶段结论

Stage 5 自动门和架构门通过，方向未偏离需求文档。按用户授权的连续推进规则，本阶段记为 `accepted`，进入 Stage 6：Volume Preview 与 Rendering。
