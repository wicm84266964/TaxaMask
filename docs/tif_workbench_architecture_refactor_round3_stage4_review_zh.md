# TIF 工作台架构整理第三轮 Stage 4 正式复核记录

日期：2026-07-10

状态：`accepted`

## 研究工作流

Full volume 绘制一个或多个关键切片矩形 → 保存/恢复 ROI 草稿 → 确认 bbox/shape/source → 同步或后台创建 part → 初始化 accepted mask → 刷新树并选择新 part。取消只处理未关联草稿，不删除已创建 part。

## 状态与 worker 所有权

`TifRoiWorkflowController` 唯一持有 active ROI、ROI keyframes、draw mode、confirm request/task/thread/worker/progress。Widget 只提供只读兼容属性，不赋值这些字段；旧 ROI 保存/确认/取消/worker wrapper 已删除。

## 工作流边界修正

正式复核发现 ROI controller 直接写 Part Mask controller 内部 state。已改为显式 command：

- `load_roi_draft_keyframes()`：由 Part Mask controller 自己加载 contour 草稿并清理 preview。
- `clear_roi_draft_keyframes()`：由 Part Mask controller 自己清理 draft/preview/accepted flag。

ROI controller 不再出现 `part_mask_workflow_controller.state`，避免两个工作流重新形成双写耦合。

## 信号与任务

- bbox text、Draw、Save、Confirm、Cancel 五条控件信号由 ROI controller 幂等绑定。
- Canvas ROI drag/overlay 双击和 confirm worker progress/finished/failed 直接进入 controller。
- confirm task context 包含 specimen/scope/part/reslice/request key；stale 结果不能创建到新 specimen。

## 数据安全

- bbox 使用 z/y/x 顺序并经 shape clip/ROI service 校验。
- accepted mask 初始化与 part 创建在 service/controller 闭环中完成。
- 草稿、accepted part 和 Part Mask preview 角色分离。
- 取消草稿不删除 accepted part，原始 TIF 不被覆盖。

## 自动门

- ROI controller/service 直接测试：6 条通过。
- `tif_core` 82、`tif_storage_safety` 16、`tif_services` 24、`tif_preview_export` 106、`tif_workbench` 249、`tif_layout` 5、`tif_architecture_round3` 2、`gui_smoke` 94、`ui_polish` 83 全部通过。
- controller 707 行，无重复方法，低于 3,000 行禁止线。

## 研究门

自动化覆盖跨切片 ROI、最新 bbox、后台 confirm、accepted preview mask、stale context、part/mask 创建和重开记录。当前未重新使用真实蚂蚁 TIF 人工操作，执行清单中旧的人工勾选不作为本次正式证据；真实 ROI 外壳和 mask 范围检查留到 Stage 10。

## 对照需求文档

状态、信号、测试、task context、数据角色和跨 controller command 同步迁移，方向符合完整工作流拆分要求。未修改 ROI 数学、项目格式或原始 TIF。

## 阶段结论

Stage 4 通过并记为 `accepted`，进入 Stage 5：Part Mask 与 Material。
