# TIF 工作台架构整理第三轮 Stage 7 正式复核记录

日期：2026-07-10

状态：`accepted`（自动门通过；真实研究设备上的清晰度验收留 Stage 10）

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 完整研究动作

选择 part → 建立 source Z / editable Z 草稿 → 点选 A/B/C roll/reference plane → 3D overlay 与 endpoint/body drag → 构建 reslice payload → 后台导出 image/mask/record → 校验 task context → 通过 Selection command 选择新 reslice → 导出 training manifest。

## 状态与信号

- 新增 `TifLocalAxisState`，唯一保存 draft、drag、pick target、export thread/worker/progress/context/task id。
- Shell 删除全部 Local Axis 默认副本；Widget descriptor 只作 Stage 9 前兼容视图。
- 9 条按钮信号由 controller 通过 Signal Router 直接绑定。
- CPU/GPU Canvas 的三点 picker、endpoint/body drag 直接调用 controller。
- Volume renderer 通过 `volume_overlays()` 读取只读 overlay。

## 主文件退场

- 原样迁移 23 个几何、overlay、hit-test、drag 方法，数学表达式不改。
- 迁移 reslice worker 生命周期、完成/失败处理和 training manifest。
- 删除 23 个 Widget 纯转发方法，并将旧测试 seam 改到 controller。
- reslice 完成后不再调用树控件私有入口，统一使用 Selection workflow command。

## 异步与数据安全修复

严格复核发现并修复三项真实问题：

1. Local Axis controller 必须继承 `QObject`，否则 worker callback 可能在后台线程直接刷新 Qt/SQLite，曾在综合 smoke 中触发 Windows access violation。
2. `export_running()` 必须保持到 `QThread.finished`，不能在 worker `finished` signal 刚发出时提前清空线程引用。
3. reslice TIFF memmap 在切换/关闭时必须显式关闭；Volume cache/renderer 先释放，再关闭数组并回收，避免 Windows 文件锁导致不能删除或重开。

stale export 完成时不 refresh project、不选择旧 reslice，当前研究焦点保持不变。

## 测试

新增/扩展 controller 直接合同 7 条：信号幂等、唯一状态、stale export、完整工作流方法、controller 规模与重复方法。

Local Axis 窄验证覆盖 service、reslice 数学、AI manifest/proposal 和 15 条关键 GUI 流程；包括 endpoint/body drag、A/B/C reference plane、preview busy lock、真实临时 reslice export、保存重开，全部通过。

## 全层自动门

- `tif_core`：82
- `tif_storage_safety`：16
- `tif_services`：24
- `tif_preview_export`：106
- `tif_workbench`：269
- `tif_layout`：5
- `tif_architecture_round3`：2
- `gui_smoke`：94
- `ui_polish`：83

合计 681 条全部通过。

## 架构指标

| 指标 | Stage 6 | Stage 7 |
| --- | ---: | ---: |
| 主文件物理行数 | 8,818 | 7,932 |
| Widget 方法数 | 478 | 427 |
| 薄方法数 | 212 | 186 |
| 主文件 `.connect()` | 113 | 96 |
| 私有测试引用次数 | 410 | 392 |
| Local Axis controller | 364 | 1,245 |

Controller 仍远低于 3,000 行硬限制，内容属于同一完整工作流。

## 需求方向复核

- 三点与 roll reference 行为保持：自动测试证明。
- preview busy lock 不误阻止点选：自动测试证明。
- stale export 不抢焦点：直接合同证明。
- reslice/training manifest 格式不变：core/service/export 测试证明。
- Local Axis 数学未重写：机械迁移并由原有数值测试覆盖。
- 真实研究样本清晰度和人工观察：留 Stage 10，不伪造结论。

## 阶段结论

Stage 7 自动门、架构门和需求方向通过，记为 `accepted`，进入 Stage 8：Training、Prediction、Result Review 与 Backend Panel。
