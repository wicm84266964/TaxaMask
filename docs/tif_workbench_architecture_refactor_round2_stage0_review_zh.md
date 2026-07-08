# TIF 工作台架构整理第二轮 Stage 0 复核记录

日期：2026-07-09

分支：`codex/tif-workbench-architecture-refactor`

对应需求文档：`docs/tif_workbench_architecture_refactor_round2_requirements_zh.md`

对应执行清单：`docs/tif_workbench_architecture_refactor_round2_execution_checklist_zh.md`

## 阶段目标

Stage 0 的目标是把第二轮开始前的工作区状态收口为一个可审计节点，避免第一轮主体、第一轮后续补丁和第二轮深拆混在一起。

## 当前 Git 状态

- 第一轮主体提交：`346598b`（`整理 TIF 工作台架构与分层回归测试`）。
- 本阶段收口内容包括：
  - 第一轮后续 UI 回归修复。
  - 右侧栏、Local Axis busy lock、翻译和 ANTCODE 对齐补丁。
  - 一键验证脚本和验证自审测试。
  - 新增 safe IO、TIF SQLite loader、PDF profile 删除安全测试。
  - 第二轮需求文档和执行清单。

## 数据安全审计

已检查 `git status --short --ignored`。本地研究数据、数据库、模型权重、运行输出和 API 配置仍处于 ignored 状态，没有进入候选提交。

明确未纳入提交的本地内容包括：

- `TaxaMask_outputs/`
- `AntSleap/weights/`
- `ant_V2.db`
- `ant_literature.db`
- `user_config.json`
- `screener_configs/api_runtime_settings.json`
- 本地 project JSON、runtime cache、`__pycache__` 和 `.tmp_validation/test_*` 验证产物

## 验证记录

使用环境：

```powershell
C:\Users\admin\anaconda3\envs\taxamask\python.exe
```

已执行：

```powershell
git diff --check
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m py_compile scripts\run_validation_suite.py tests\test_validation_suite_script.py tests\test_safe_io.py tests\test_tif_sqlite_loader.py tests\test_pdf_profile_deletion_safety.py tests\test_tif_workbench.py AntSleap\ui\tif_workbench.py AntSleap\core\panel_splitter.py
C:\Users\admin\anaconda3\envs\taxamask\python.exe scripts\run_validation_suite.py --timeout 300
```

结果：

- `git diff --check` 通过，仅有 Windows LF-to-CRLF 工作区提示。
- `py_compile` 通过。
- 一键全量验证通过：15 个套件，962 个测试函数。
- `gui_smoke` 和 `ui_polish` 已采用分块运行，避免 GUI 测试进程收尾导致全量验证中断。

## 人工验收状态

截至 Stage 0：

- 主界面人工冒烟通过：未再看到训练/预测英文漏翻译。
- 右侧栏人工观察通过：最大化后未见溢出。
- Local Axis 三点参考和重切片在全量验证前已由用户确认可用。
- GPU/3D preview 深验收因后台训练占用资源暂未完整覆盖。
- 曾出现 `WinError 1455 页面文件太小`，经排查为 Windows 提交内存耗尽和旧 multiprocessing worker 残留导致；已清理孤儿 worker，第二轮已将该问题写入注意事项和资源控制器目标。

## 阶段结论

Stage 0 通过。当前状态适合作为第二轮深拆前的本地提交节点。下一阶段应从 Layout / 页面骨架拆分开始，并严格保持每阶段验证和提交。
