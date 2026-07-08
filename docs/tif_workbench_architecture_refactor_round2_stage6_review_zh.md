# TIF 工作台架构整理第二轮 Stage 6 收口复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 6 目标是把第二轮架构整理收束为一个可审计候选版本：确认各阶段改动已经经过自动化验证，确认没有把本地研究数据或测试产物混入 Git，并对照第二轮需求文档检查方向是否偏离。

## 本阶段改动

文档与流程收口：

- 在执行清单中新增“执行中强制检查点”，把第一轮和第二轮中已经踩过的坑写成后续阶段必须检查的事项。
- 新增本 Stage 6 复核记录，集中记录全量验证、需求方向核对、剩余人工验收点和候选版本判断。

未改动：

- 不修改 TIF 项目数据格式。
- 不修改训练/预测后端。
- 不修改 Local Axis 重切片算法。
- 不修改 label sidecar、manual truth、prediction draft、raw backup 的核心规则。

## 自动化验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行导入/语法检查：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile AntSleap\ui\tif_workbench.py AntSleap\ui\tif_workbench_layout.py AntSleap\ui\tif_workbench_pages.py AntSleap\ui\tif_workbench_control_panels.py AntSleap\ui\tif_backend_panel_controller.py AntSleap\ui\tif_preview_controller.py AntSleap\ui\tif_local_axis_controller.py AntSleap\ui\tif_agent_context.py AntSleap\ui\tif_workbench_style.py AntSleap\core\tif_resource_policy.py scripts\run_validation_suite.py
```

结果：通过。

已执行全量验证：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --timeout 300
```

结果：通过，合计 982 条测试通过。

套件结果：

- `tif_core`：82 条通过。
- `tif_storage_safety`：16 条通过。
- `tif_services`：24 条通过。
- `tif_preview_export`：106 条通过。
- `tif_model_backends`：31 条通过。
- `tif_workbench`：229 条通过。
- `gui_smoke`：94 条通过，按 chunk 分块执行。
- `ui_polish`：83 条通过，按 chunk 分块执行。
- `tif_layout`：5 条通过。
- `pdf_safety`：4 条通过。
- `validation_tooling`：4 条通过。
- `sqlite_2d`：38 条通过。
- `agentic_misc`：64 条通过。
- `blink_locator`：103 条通过。
- `pdf_literature`：44 条通过。
- `generic_vlm_stl`：55 条通过。

验证后已清理：

- `.tmp_validation` 下的一次性测试数据库和 artifacts。
- Python `__pycache__` 缓存。

## 第二轮需求方向核对

### Layout / Page 层

状态：已完成。

证据：

- 新增 `AntSleap/ui/tif_workbench_layout.py`。
- 新增 `AntSleap/ui/tif_workbench_pages.py`。
- 新增 `AntSleap/ui/tif_workbench_control_panels.py`。
- 新增 `tests/test_tif_workbench_layout.py`。
- `tif_layout`、`gui_smoke`、`ui_polish` 和 `tif_workbench` 套件通过。

研究流程影响：

- 控件装配从主 Widget 中移出，右侧栏、页面栈和控件 objectName 有测试保护。
- 后续增加 TIF 页面控件时，更容易判断问题属于 UI 布局还是标注/训练业务规则。

### Training / Prediction UI Controller

状态：已完成。

证据：

- 新增 `AntSleap/ui/tif_backend_panel_controller.py`。
- 新增 `tests/test_tif_backend_panel_controller.py`。
- `tif_model_backends`、`tif_services`、`tif_workbench` 套件通过。

研究流程影响：

- 训练/预测按钮状态、模型库刷新、训练样本诊断和预测导入入口更集中。
- UI 仍调用已有 service/core guard，不绕过 manual truth、prediction draft 和 raw backup 保护。

### Preview / GPU Resource Controller

状态：已完成。

证据：

- 新增 `AntSleap/ui/tif_preview_controller.py`。
- 新增 `AntSleap/core/tif_resource_policy.py`。
- 新增 `tests/test_tif_resource_policy.py`。
- 新增 `tests/test_tif_preview_controller.py`。
- `tif_preview_export` 和 `tif_workbench` 套件通过。

研究流程影响：

- `WinError 1455`、内存不足、memmap 打开失败、OpenGL/显卡相关失败有统一分类。
- 资源不足时倾向给出可理解提示，避免用户把页面文件/提交内存问题误判为 TIF 数据损坏。

### Local Axis UI Controller

状态：已完成。

证据：

- 新增 `AntSleap/ui/tif_local_axis_controller.py`。
- 新增 `tests/test_tif_local_axis_controller.py`。
- `tif_preview_export` 和 `tif_workbench` 套件通过。

研究流程影响：

- 三点参考、观察侧剖切面、roll reference、导出按钮状态和 payload 准备从主 Widget 中拆出。
- 保留关键规则：preview busy lock 不阻止 Local Axis 三点草稿交互。

### 主 Widget 收束

状态：部分完成。

证据：

- 新增 `AntSleap/ui/tif_workbench_style.py`。
- 新增 `AntSleap/ui/tif_agent_context.py`。
- 新增 `tests/test_tif_workbench_style.py`。
- 新增 `tests/test_tif_agent_context.py`。
- `get_agent_context()`、样式表和 canvas 背景逻辑已从主文件移出。
- `tif_workbench.py` 第二轮前置基线约 14,694 行；当前约 13,388 行；第二轮累计减少约 1,306 行。

未完全达到的点：

- 执行清单中“减少 2500-4000 行”的理想目标未达到。
- 没有继续机械拆分 label 保存、part mask、Local Axis overlay、真实导出 worker 等高风险链路。

原因：

- 这些链路直接影响研究数据写入、manual truth 安全、重切片结果和训练入口。
- 在真实 GPU/TIF 全链路人工验收不足前，继续强行拆深会显著增加回归风险。
- 当前第二轮更合理的收口点是“核心 UI 方向都已拆出，主文件明显变薄，剩余高风险业务链路留给下一轮按真实验收推进”。

## 执行清单完成判断

对照“第二轮完成判断”：

- 至少 layout、backend panel、preview、Local Axis 四个方向中完成三个：已完成四个。
- `tif_workbench.py` 职责密度明显下降：已下降，主文件约减少 1,306 行，并移出 layout、backend panel、preview、Local Axis、style、Agent context 等职责。
- 训练/预测、3D preview、Local Axis 的 UI 状态更容易单独测试：已达成，新增 controller/resource/style/context 测试并纳入一键验证。
- 资源不足错误能被用户理解并恢复：代码层已建立分类和提示；真实极端资源场景仍建议人工复测。
- 第一轮数据安全和任务生命周期收益没有回退：自动化测试通过，未改动数据格式和核心 guard。
- 用户完成真实项目人工验收后确认可以合并：仍需要用户最终确认。

## 剩余人工验收点

自动化测试无法完全替代以下真实研究链路，需要在合并前由用户用真实项目确认：

- 打开真实 TIF 项目，切换 specimen / part / reslice。
- 显卡空闲时查看 3D volume preview、mask preview、part preview。
- Local Axis 三个参考点可点选。
- 观察侧剖切面可用于 roll reference。
- 执行一次真实重切片导出。
- 保存项目并重开，确认 reslice 记录仍在。
- 训练/预测页面中文按钮、模型库、训练样本诊断和预测入口显示正常。
- 如后台训练正在运行，确认资源不足提示可理解，程序不把页面文件不足当成数据损坏。

## 已纳入后续避坑清单

执行清单已经补充“执行中强制检查点”，后续阶段必须主动避免：

- 误用默认 Python 环境并安装 PySide6。
- 只看程序能启动，不看右侧栏、翻译、Local Axis、重切片、训练/预测入口。
- 改 preview busy lock 后再次挡住 Local Axis 三点。
- 把 `WinError 1455` 误判为数据损坏。
- 清理残留时误杀有效训练任务。
- 新增测试后忘记加入一键验证脚本。
- Agent/AntCode 状态字段变化后不同步对接输出。
- 提交时混入 TIF、SQLite、模型权重、run outputs 或 API 配置。

## 量化结论

- 第二轮执行清单中的代码/测试阶段完成度：约 95%。
- 第二轮需求文档方向完成度：约 88%。
- 主文件行数下降：约 1,306 行，约为第二轮前置基线的 8.9%。
- 四个主要拆分方向完成度：4/4。
- 全量自动化验证通过率：982/982。
- 仍需人工验收覆盖度：约 10%-12%，主要集中在真实 GPU、真实 TIF、真实训练/预测输出导入这些无法由无头测试完全证明的链路。

## 阶段结论

Stage 6 自动化收口通过。第二轮没有偏离需求文档：方向仍是把 TIF 工作台从巨型 Widget 继续拆成 layout、controller、resource policy、Agent context 和 style 等更清晰的结构，同时保护真实标注、训练、预测和重切片研究流程。

当前版本可作为第二轮候选版本进入用户真实 TIF/GPU 人工验收；人工验收通过后，适合作为本分支的阶段性合并候选。
