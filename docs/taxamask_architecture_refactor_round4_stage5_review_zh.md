# TaxaMask 第四轮架构优化 Stage 5 正式复核记录

日期：2026-07-11

状态：`verified`；按用户连续执行授权进入 Stage 6，不推送 GitHub

## 1. 本阶段范围

Stage 5 将 2D 图像导航、部位树和文献描述桥接从 `AntSleap/main.py` 迁入独立 mixin：

- `main_window_part_tree.py`：taxonomy、parent-child 部位树、图片/部位选择。
- `main_window_image_navigation.py`：图片导入、panel split、crop provenance、图片分组、文件列表和删除恢复。
- `main_window_literature_bridge.py`：PDF/STL 来源定位、分类单元匹配和文献描述应用。
- `main_window_navigation_dependencies.py`：以上模块共用的显式依赖。

Blink context、SAM、标注、训练、预测、VLM 和导出仍留在后续 Stage 6-7。本阶段没有进入 TIF 工作台内部已验收架构。

## 2. 研究流程与数据安全

- 图片删除仍先确认，再以 `save=False` 批量修改项目，并通过延迟保存边界写入 SQLite。
- 删除当前图片后仍选择下一张；删除末尾图片后选择上一张，不会留下指向已删除记录的当前选择。
- 图片分组只更新 provenance 中的 `manual_image_group`，不改变标注、AI 草稿或训练真值角色。
- panel split 继续保留原图、派生图和人工复核状态，不改变 crop provenance 语义。
- 文献描述优先使用当前图片产物对应的数据库，避免错误借用 PDF 工作台当前打开的另一数据库。
- 同一图片再次被选中时不重新加载 pixmap，也不触发导航保存延迟；标签、框和界面状态仍按当前项目数据刷新。

## 3. 测试与信号对接

迁移后的测试替换点已指向真实实现模块：

- `ImageImportThread`、图片删除确认、panel split 确认和文件菜单改为 patch `main_window_image_navigation`。
- taxonomy 删除确认改为 patch `main_window_part_tree`。
- 测试不要求生产代码反向读取 `main.py` 的旧全局变量。

新增 `test_main_window_stage5_navigation.py`，验证方法身份、新模块无 MainWindow 反向导入、同图不重复加载和分组单次延迟保存。架构分析已扫描三个新模块；第四轮真实连接总数保持 194 条。

## 4. 结构变化

| 指标 | Stage 4 | Stage 5 | 变化 |
| --- | ---: | ---: | ---: |
| `main.py` 物理行 | 7,207 | 5,113 | -2,094（-29.1%） |
| MainWindow 直接类体 | 6,703 | 4,603 | -2,100（-31.3%） |
| MainWindow 直接方法 | 283 | 189 | -94（-33.2%） |
| MainWindow 直接连接 | 51 | 44 | -7 |
| 第四轮架构总连接 | 194 | 194 | 0 |

Stage 0 至 Stage 5，`main.py` 从 16,024 行降到 5,113 行，减少 10,911 行（68.1%）。

## 5. 性能

10 个独立进程样本；8 个正常退出，2 个在完整结果打印后出现已知 offscreen Qt return code `3221226505`。基准工具现在接受已完整产出的样本，同时把异常退出码写入报告，不再把可用测量误判为未执行。

| 指标 | Stage 4 | Stage 5 | 变化 |
| --- | ---: | ---: | ---: |
| Start Center 中位数 | 4,238.036 ms | 4,177.341 ms | -1.4% |
| Start Center P95 | 4,341.384 ms | 4,885.465 ms | +12.5% |
| import 中位数 | 4,113.548 ms | 4,054.148 ms | -1.4% |
| MainWindow 构造 | 118.656 ms | 116.530 ms | -1.8% |
| 小型 2D 项目打开 | 12.933 ms | 12.587 ms | -2.7% |
| 首次进入 TIF | 334.902 ms | 330.622 ms | -1.3% |
| Start Center RSS | 573.266 MB | 573.297 MB | +0.01% |

Stage 5 图片切换中位数为 0.381 ms、P95 为 0.425 ms；部位切换中位数为 0.249 ms、P95 为 0.283 ms。小 fixture 不代表用户大型真实项目，但能够证明本次纯迁移没有引入同步阻塞。Start Center P95 受第一次冷启动 4.885 秒影响，未达到“P95 不回退超过 10%”目标，作为真实波动保留，Stage 8-9 继续复测。

## 6. 自动化验证

- 第四轮架构套件：34 条通过。
- GUI smoke：94 条按 3 条隔离分块全部通过。
- UI polish：83 条按 5 条隔离分块全部通过。
- 2D SQLite：38 条通过。
- PDF/literature：44 条通过。
- generic VLM/STL：55 条通过。
- Stage 5 聚焦导航集合：11 条通过。
- 新增/修改 Python 文件 `py_compile` 通过，`git diff --check` 通过。

## 7. 结论

Stage 5 达到 `verified`。图片、部位、分组、panel split 和文献来源链路已经对接迁移后的真实模块；保存边界和研究数据角色保持不变。按连续执行授权形成独立本地提交后进入 Stage 6：Annotation、SAM 与 Blink。
