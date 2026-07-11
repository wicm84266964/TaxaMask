# TaxaMask 第四轮架构优化 Stage 9 自动终验记录

日期：2026-07-11

状态：`automation verified / researcher acceptance pending`；不推送 GitHub

## 1. 完整自动化

使用 `C:\Users\admin\anaconda3\envs\taxamask\python.exe` 和 offscreen/software OpenGL 运行 `scripts/run_validation_suite.py --timeout 180`。

| Suite | 测试数 | 结果 |
| --- | ---: | --- |
| tif_core | 90 | 通过 |
| tif_storage_safety | 16 | 通过 |
| tif_services | 25 | 通过 |
| tif_preview_export | 108 | 通过 |
| tif_model_backends | 31 | 通过 |
| tif_workbench | 318 | 317 通过，1 条环境相关 skip |
| gui_smoke | 94 | 通过；每 3 条隔离分块 |
| ui_polish | 83 | 通过；每 5 条隔离分块 |
| tif_layout | 5 | 通过 |
| pdf_safety | 4 | 通过 |
| validation_tooling | 4 | 通过 |
| tif_architecture_round3 | 4 | 通过 |
| taxamask_architecture_round4 | 54 | 通过 |
| sqlite_2d | 38 | 通过 |
| agentic_misc | 67 | 通过 |
| blink_locator | 103 | 通过 |
| pdf_literature | 44 | 通过 |
| generic_vlm_stl | 55 | 通过 |

总计 18 个 suite、1,143 条测试；1 条环境相关 skip，其余通过。

## 2. 静态与文档终验

- `AntSleap/`、`core/`、`tools/`、`scripts/`、`tests/` 全目录 `compileall` 通过。
- Stage 1-8 公开 import、方法身份、无 MainWindow 反向导入 contract 共 48 条复核通过。
- Agent labeling route 已从旧 `main.py` 方法改到 annotation、Blink context 和 VLM workflow owner，并新增回归测试。
- Gate E 现场发现首轮 `list_files` 返回 3,439,325 字节目录清单，使 8 条消息膨胀到约 3.69 MB 并触发自动压缩；现统一将单次工具结果限制为 256 KiB，并保留截断后的工具成功/失败状态。
- 相同真实目录运行态复测：工具结果 262,144 字节，会话 70,547 个估算 token，`compacted=0`，两轮完成并返回 161 字节中文正文。真正无正文且无工具调用的网关响应会强制进行一次正文修复重试。
- 架构连接总数 194；MainWindow 类体直接连接 0。
- `git diff --check` 通过。
- `.tmp_validation/` 已清理。
- `LLM_CONTEXT_DETAILED.md`、`CHANGELOG_zh.md` 和现有 2.3.0 release note 已同步。
- README 的产品定位、安装方式和工作流入口未变化，因此不修改。

## 3. 候选结构

- `main.py`：763 行。
- MainWindow 类体：36 行。
- MainWindow 直接方法：1 个构造器。
- MainWindow 直接状态写入：0。
- MainWindow 直接 Qt 连接：0。
- 真实架构连接：194。
- 最大 workflow 模块：1,392 行。
- MainWindow 直接私有实现测试引用：0。

## 4. 剩余风险

- 自动化无法替代真实大型 2D SQLite、真实训练/VLM API、真实 TIF stack 和本机 GPU/CPU renderer 的可见验收。
- Start Center、图片/部位微基准、首次惰性 TIF 创建和 RSS 未达到全部 stretch 目标，真实数据见 Stage 8 review。
- offscreen 性能子进程有已知 Windows/Qt `3221226505` 退出波动；完整 GUI 分块测试正常通过，不应把两者混为业务崩溃已经复现。
- workflow owner 当前采用 mixin 兼容结构，并非全部转换为独立 port/controller；不要在后续维护中把逻辑重新堆回 `main.py`。

## 5. 结论

Stage 9 自动化终验达到 `verified`。候选尚未标记 `accepted`，等待研究者按 `docs/taxamask_architecture_refactor_round4_acceptance_zh.md` 完成真实流程验收。验收前不合并 `main`、不推送、不创建新 Release。
