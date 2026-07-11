# TaxaMask 第四轮架构优化 Stage 6 正式复核记录

日期：2026-07-11

状态：`verified`；按用户连续执行授权进入 Stage 7，不推送 GitHub

## 1. 本阶段范围

Stage 6 将 2D 标注、SAM 和 Blink 从 `AntSleap/main.py` 迁入三个独立 mixin：

- `main_window_annotation.py`：manual box/polygon、SAM point/box prompt、回调、比例尺和形态测量。
- `main_window_blink_context.py`：parent-child 解析、route 状态、工作台上下文和 Blink 入口。
- `main_window_blink_workflow.py`：child auto annotate、auto shrink、batch shrink、子专家训练和停止。
- `main_window_stage6_dependencies.py`：上述模块共享的显式依赖。

训练主流程、prediction、VLM 和 dataset export 保留给 Stage 7。TIF volume 与 TIF Local Axis 内部实现未修改。

## 2. 研究数据安全

- manual polygon/box 仍以 `save=False` 修改当前 2D 项目，再进入统一延迟保存边界。
- SAM prompt 固定发起时的 image、part 和 description；即使研究者在推理完成前切换图片，结果仍写回原图片，不污染当前新图片。
- SAM 失败会清空 busy 与 pending context，避免后续提示误用旧部位。
- Blink shrink loose box 与 child manual ROI box 继续分开保存，训练轨迹和人工标注角色不混用。
- child auto annotate 继续先由 appointed route expert 产生 child box，再由 base SAM 生成 polygon；结果仍是待复核草稿。
- batch auto shrink 跳过已有 trajectory 的图片，不覆盖已存在训练轨迹。
- 子专家训练 progress/result/error/cancelled/finished 信号只连接一次，避免重复写状态或重复完成通知。

## 3. 后端隔离

- Parent 2D/STL 仍由 parent locator/segmenter profile 决定。
- Blink child 仍由 cascade route 的 appointed expert 和 child backend 决定。
- TIF volume 与 TIF Local Axis 仍由各自 TIF backend contract 决定。
- Stage 6 没有把 Blink child 配置写入 parent 或 TIF backend，也没有修改模型 contract、SQLite schema 或训练算法。

## 4. 测试与依赖迁移

测试替换点已迁到真实实现模块：

- SAMWorker/QThread 改为 patch `main_window_annotation`。
- Blink batch shrink 确认框改为 patch `main_window_blink_workflow`。
- BlinkEntryDialog 改为 patch `main_window_blink_context`。

新增 `test_main_window_stage6_annotation_blink.py`，验证方法身份、无 MainWindow 反向导入、SAM stale context 和子训练信号单次连接。三个新模块通过字节码 `LOAD_GLOBAL` 审计，未发现未声明依赖。第四轮真实连接总数保持 194 条。

## 5. 结构变化

| 指标 | Stage 5 | Stage 6 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 5,113 | 3,932 | -1,181（-23.1%） |
| MainWindow 直接类体 | 4,603 | 3,416 | -1,187（-25.8%） |
| MainWindow 直接方法 | 189 | 130 | -59（-31.2%） |
| MainWindow 直接连接 | 44 | 32 | -12 |
| 第四轮架构总连接 | 194 | 194 | 0 |

Stage 0 至 Stage 6，`main.py` 从 16,024 行降到 3,932 行，减少 12,092 行（75.5%）。

## 6. 性能

10 个独立进程样本；9 个正常退出，1 个在完整结果打印后出现已记录的 offscreen Qt return code `3221226505`。

| 指标 | Stage 5 | Stage 6 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 中位数 | 4,177.341 ms | 4,253.760 ms | +1.8% |
| Start Center P95 | 4,885.465 ms | 4,989.076 ms | +2.1% |
| import 中位数 | 4,054.148 ms | 4,131.069 ms | +1.9% |
| MainWindow 构造 | 116.530 ms | 117.242 ms | +0.6% |
| 小型 2D 项目打开 | 12.587 ms | 12.420 ms | -1.3% |
| 图片切换 | 0.381 ms | 0.389 ms | +2.1% |
| 部位切换 | 0.249 ms | 0.252 ms | +1.5% |
| 首次进入 TIF | 330.622 ms | 333.978 ms | +1.0% |
| Start Center RSS | 573.297 MB | 573.135 MB | -0.03% |

所有纯迁移路径中位数回退低于 5%，P95 回退低于 10%。小 fixture 不替代 Stage 9 的真实大型项目人工验收。

## 7. 自动化验证

- 第四轮架构套件：39 条通过。
- Blink/locator：103 条通过。
- Agent/SAM 与通用运行时：64 条通过。
- GUI smoke：94 条按 3 条隔离分块全部通过。
- UI polish：83 条按 5 条隔离分块全部通过。
- Stage 6 GUI key-path：19 条通过。
- TIF model backends：31 条通过。
- generic VLM/STL：55 条通过。
- 新增/修改 Python 文件 `py_compile` 通过，`git diff --check` 通过。

## 8. 结论

Stage 6 达到 `verified`。SAM 与 Blink 的异步上下文、信号生命周期和研究数据角色保持安全，四类模型后端仍相互独立。按连续执行授权形成独立本地提交后进入 Stage 7：Training、Prediction、VLM 与 Export。
