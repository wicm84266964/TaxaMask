# TIF 工作台架构整理第三轮 Stage 10 正式复核记录

日期：2026-07-10

状态：`accepted`（自动门、隔离真实蚂蚁体积、真实 CUDA 预测、可见 3D、Local Axis 解剖方向和 Dataset601 脑区边界均通过）

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

## 自动验收结果

- 使用真实 GUI 环境 `C:\Users\admin\anaconda3\envs\taxamask\python.exe`，没有把缺少 PySide6 的 base Python 跳过结果当作通过。
- 对最终 Git 修改和新增的 46 个 Python 文件执行 `py_compile`，全部通过。
- 运行 67 条 responsibility/signal/state/suite registration 合同测试，全部通过。
- 最终九组验证显式启用真实 fixture：`tif_core` 83、`tif_storage_safety` 16、`tif_services` 24、`tif_preview_export` 106、`tif_workbench` 287、`tif_layout` 5、`tif_architecture_round3` 4、`gui_smoke` 94、`ui_polish` 83，共 702 条全部通过。
- `git diff --check` 通过。
- Git 状态未发现 TIF/TIFF、SQLite/数据库、模型权重、run output、API 配置或 JSON 数据产物进入候选变更。
- 清理 28 个本轮明确创建的 `.tmp_validation` 临时指标/代码块文件；未删除来源不明确的既有调试材料。

## Stage 10 发现并修复的验证缺口

- `tests/test_tif_preview_controller.py` 仍调用已删除 Widget seam，已迁到 Preview controller 公共入口，并在真实 Qt 环境下通过。
- 架构测试原先要求主文件必须存在按钮 `clicked` 信号，与“按钮直连 controller、删除 Widget 转发层”的需求相冲突；现改为要求保留必要 renderer/thread 信号且禁止主文件按钮 `clicked`。
- ROI controller 测试曾漏登 `tif_workbench` suite；Volume Render controller 测试曾漏登架构 GUI 分组。两处均已补齐，并通过验证脚本默认覆盖合同测试。
- 新增 `tests/test_tif_round3_real_data_acceptance.py`：只有显式设置 `TAXAMASK_REAL_TIF_FIXTURE` 才运行；所有写入发生在 `.tmp_validation` 隔离 SQLite 项目，真实源 sidecar 只读，并以 SHA-256 树哈希前后一致证明未被修改。
- 使用现有真实蚂蚁体积 `22-38/part_1`（11×144×104，uint8）完成真实体积加载、两个 specimen 往返、跨关键切片 mask、ROI-to-Part、accepted mask、部位标注保存、Local Axis reslice、SQLite 重开与 specimen/part/reslice 选择恢复。
- 同一真实数据链进一步证明：自动保存快照后同切片继续编辑保留较新 revision/dirty；材料 3 可跨切片保存并重开；mask preview 可清除、修改关键切片后重建不同结果并接受；旧 Preview 在切换 specimen 后被取消且不覆盖既有 cache 或当前选择；part editable result 经 Truth Promotion 生成 manual truth 时 raw prediction backup 保持不变；真实尺寸外部 prediction 正确 shape 可导入、错误 shape 被拒绝且 manual truth 不变；训练诊断在缺少 reslice record/image 时准确阻止选择，无登记模型时模型库保持空状态。
- 离屏实机 renderer 探测为 `CPU fallback`；状态文字、真实 source shape 和性能报告正常。此证据不替代可见窗口中的 GPU 视觉验收。
- 使用 Dataset601 自身匹配的真实蚂蚁脑体积（647×647×195，spacing 0.6×0.6×约 0.999 µm）、`dataset601_standard_300_best` 模型、`3d-brain` CUDA 环境和 GPU 0，经生产 `TifBackendRunner` 完成真实 nnU-Net 预测；225 个 sliding-window step 完成，`returncode=0`，输出包含 17 个标签值和 11,399,129 个非背景体素。
- 预测产物仅写入 `.tmp_validation` 隔离 SQLite 项目，输入 NIfTI SHA-256 前后一致；contract 使用 `input_label_role=none` 和 `protect_manual_truth=true`，结果登记为 `working_edit/pending_review`、`raw_ai_prediction_backup/raw_backup` 和 model draft，未生成或覆盖 manual truth。
- 真实 GPU 重开复核发现顶层 `raw_ai_prediction_backup` 文件虽存在，但 SQLite writer 漏写该角色记录；已在 `AntSleap/core/tif_sqlite_migration.py` 修复角色白名单，并在 JSON→SQLite 迁移测试及 nnU-Net top-level prediction 测试中加入重开断言。修复后再次执行真实 GPU 预测，SQLite 重开可恢复 raw backup 路径、角色、状态和 prediction_id。

## 最终架构指标

| 指标 | 发布基线 | Stage 10 候选 |
| --- | ---: | ---: |
| 主文件物理行数 | 14,234 | 5,056 |
| Widget 方法数 | 约 664 | 221 |
| 4 行以内方法 | 约 147 | 39 |
| 主文件 `.connect()` | 约 251 | 11 |
| `__init__` | 混合状态/控件/布局/信号 | 11 行 |
| `_build_layout` | 主文件内 | 已移出 |

主文件比 7,500–9,000 目标更小，但所有拆出部分都有明确 owner、直接测试和全层回归保护；没有删除错误处理、翻译、审计信息或研究安全规则来换取行数。

## 研究数据安全复核

- 项目格式和 SQLite schema 未修改。
- 原始 TIF 不作为可写标签目标。
- working edit、manual truth、raw prediction、accepted mask 的角色和 promotion guard 未改变；顶层 raw prediction backup 现在可在 SQLite 重开后完整恢复。
- 外部 prediction 导入测试证明 manual truth 不被覆盖。
- 自动保存失败继续保留 dirty/retry 语义；后台 stale result 不刷新新选择或写入新上下文。
- ROI、mask、reslice、训练和 prediction 继续通过既有 service/core guard；训练算法、Local Axis 数学和 GPU renderer 数学未修改。

## 真实数据已验证与待用户观察

已在隔离副本完成：真实蚂蚁体积加载、多 specimen 往返、自动保存并发 revision、材料跨切片持久化、mask preview 清除/重建/接受、ROI-to-Part、部位标注保存、stale Preview 切换保护、Local Axis reslice、SQLite 重开和 part/reslice 选择恢复；源 sidecar 哈希前后完全一致。

可见技术链已在隔离真实项目完成：下拉框、内部显示模式、实际 volume canvas 和加载完成反馈一致；真实 294×294×284 头部在 CPU 3D fallback 中显示 mask 内图像，输出 Z、Roll A/B、平面 C 和 overlay 均可见。本机 OpenGL renderer 初始化不稳定时，CPU fallback 正常恢复且未把 renderer 问题误报为数据损坏。

用户已完成两项不可由自动测试替代的科研判断：

1. 真实 24-43 头部的输出 Z、Roll A/B 和平面 C 符合蚂蚁头部解剖方向。
2. Dataset601 真实 GPU prediction 的脑区边界合理；结果仍保持 working edit/pending review，本轮不自动写 manual truth。

如后续计划在本机依赖 OpenGL ray march，而非正式 CPU fallback，需要单独处理驱动/Qt OpenGL 初始化兼容性；这不影响本轮 accepted 的数据安全、2D 标注或 CPU 3D 结论。

## 人工验收入口

Local Axis 解剖方向和 Dataset601 模型结果科研判断均已由用户完成。可选真实训练体验与本机 OpenGL 兼容性作为后续独立专项，不阻塞本轮 accepted。

## 候选结论

第三轮代码拆分、状态唯一性、信号迁移、测试迁移、主文件量化目标、自动化安全门、隔离真实蚂蚁体积闭环、真实 GPU 预测、可见 3D、Local Axis 解剖方向和 Dataset601 脑区科研判断全部完成。最终九组自动门共 702 条通过，本轮状态记为 `accepted`。根目录 `CHANGELOG_zh.md` 和 `LLM_CONTEXT_DETAILED.md` 已同步。

## Dataset601 多切片科研复核材料

- 中间 Z 切片彩色叠加与九层 Z 方向总览均已生成；来源为 working edit，状态为 pending review，未创建 manual truth。
- 九切片总览：`.tmp_validation/round3_manual_acceptance/dataset601_prediction_9slice_overview.png`。
- 切片索引和每层标签清单：`.tmp_validation/round3_manual_acceptance/dataset601_prediction_9slice_overview.json`。
- 预测实际出现 17 个标签值；模型清单中的 OC、unmapped_10、unmapped_16 在该预测中未出现。该事实用于研究判断，不自动解释为模型错误或正确。
- image、working edit、raw backup 的实际与登记 shape 均为 647×647×195；已修复 manual truth 缺失时重复报告 `manual_truth_missing` 并误报 `image_label_shape_mismatch` 的诊断问题。

## Accepted 后续修复：部位绑定标签表重开恢复

- 用户发现“绑定到当前部位”后重开程序，下拉框没有恢复该部位绑定的标签表。
- 数据写入本身正确：`part.training.label_schema_id` 已保存到 SQLite；根因是 `_populate_label_schema_combo()` 重开/切换 part 时优先保留控件上一次选择，而不是当前 part 的绑定值。
- 修复后，进入 part/reslice 时以当前 part 的 `training.label_schema_id` 为最高优先级；非 part 视图仍可保留用户在标签表管理区临时浏览的选择。
- 新增关闭 Widget、重开 SQLite 项目、重新进入 part 的回归，验证 combo、schema id 编辑框和标签行均恢复绑定 schema。
- 最终九组验证更新为 **703 条全部通过**。

## Accepted 后续修复：三维体预览信号归属

- 用户切换“三维体预览”时触发 `AttributeError: TifWorkbenchWidget has no attribute _on_gpu_volume_failed`。
- 根因是第三轮已将 GPU 失败、renderer 信息和渲染统计处理迁入 `TifVolumeRenderController`，但懒加载 GPU 画布时仍尝试连接已删除的 Widget 旧方法。
- 修复后，`render_failed`、`render_info_changed`、`render_stats_changed` 三类信号直接连接 `TifVolumeRenderController`；没有恢复 Widget 转发 wrapper，责任边界与第三轮架构保持一致。
- 新增真实显示模式切换回归，模拟 GPU 画布三类 Qt Signal 并验证 controller handler 各收到一次，同时明确 Widget 不再需要旧 GPU 回调。
- 相关模块 232 条通过；最终九组验证更新为 **704 条全部通过**。该修复不修改 TIF、标注、mask、manual truth、raw prediction、训练数据或 renderer 数学。

## Accepted 后续修复：GPU 三维画布鼠标交互路由

- 用户进入三维体预览后拖动鼠标，QLabel GPU 画布仍调用已删除的 `TifWorkbenchWidget.rotate_volume_preview`，触发 Python override 异常。
- 扫描确认两套 GPU 画布（offscreen QLabel 与 embedded QOpenGLWidget）共有 8 处同类遗留，覆盖旋转、平移、释放后的 still render 调度和滚轮缩放。
- 现已全部改为直接调用 `TifVolumeRenderController`，与 CPU 画布既有路由一致；Local Axis endpoint 拖动继续由 `TifLocalAxisController` 负责。
- 新增双 GPU 画布交互回归，逐一验证左键旋转、右键平移、释放和滚轮缩放均进入 controller，且不依赖 Widget 旧方法。
- 三维相关 47 条、完整相关模块 270 条通过；最终九组验证更新为 **705 条全部通过**。修复不改变 renderer 数学、体数据、标注、mask、manual truth、raw prediction 或训练状态。

## Accepted 后续优化：左侧个体与 Part 切换响应

- 用户反馈左侧树切换个体或 Part 时会出现短暂无响应。真实项目只读 profiling 显示，较大个体首次切换约 0.715 秒：主要由图像/编辑层磁盘映射和同一切片重复绘制造成。
- 选择加载原先会先由 `_reload_label_volume()` 绘制一次，完成其余面板刷新后再绘制一次；现改为加载阶段不立即绘制，所有状态就绪后统一绘制一次。
- 当前显示角色为 `working_edit` 或 Part 的 `editable_ai_result` 时，显示标签层现在复用已打开的 copy-on-write 编辑映射，不再为同一个文件额外建立只读映射；释放逻辑按对象去重，避免共享映射被重复关闭。
- 没有改动百分位灰度归一化、标注保存、manual truth、预测角色或后台加载模型，避免为了表面流畅引入显示差异或标注竞态。
- 同一真实项目热切换由约 0.715 秒降至约 0.099 秒；首次打开大型个体约 0.639 秒，剩余主要是 Windows 首次建立图像和编辑层磁盘映射。
- 新增单次映射、单次绘制、共享映射单次释放回归；相关模块 283 条通过，最终九组验证更新为 **707 条全部通过**。

## Accepted 后续优化：超大重切片三维选择不阻塞

- 用户进一步确认普通个体/Part 切换已顺畅，但截图中的具体 reslice 条目仍短暂无响应。对应磁盘产物为 GAGA-02-09 / roi_1 重切片，image.tif 约 1.72 GB、mask.tif 约 3.45 GB。
- 只读 profiling 证明 TIFF memmap 本身约 0.002–0.003 秒；真正阻塞是选择过程中多个控件信号（包括 Local Axis overlay）提前触发三维重绘，导致 1.72 GB 体数据在 GUI 线程同步降采样约 3.8 秒。完整点击路径实测约 4–7.5 秒。
- 现规定只要个体/Part/reslice 选择仍处于加载状态，所有三维重绘请求只登记 pending，不执行；选择完成后把多次请求合并为一次，并在下一轮 Qt 事件启动既有后台预览构建。
- 使用同一 1.72 GB reslice 临时挂入内存项目、不开启数据库写入复测：`load_part()` 返回约 0.016 秒，下一轮事件约 0.001 秒启动后台预览线程。三维质量、Local Axis overlay 和降采样算法均未修改。
- 更新真实数据验收契约为“选择完成后下一轮事件开始预览”，并继续严格检查 stale task 取消、旧缓存不被覆盖和源数据哈希不变。相关模块 287 条通过，最终九组验证更新为 **709 条全部通过**。

## Accepted 后续优化：带标注超大重切片 GPU 流式预览

- 用户继续发现只有 `GAGA-02-09 / roi_1` 重切片仍有短暂停顿。磁盘核对确认该条目除约 1.72 GB `image.tif` 和约 3.45 GB `mask.tif` 外，还包含约 3.45 GB 的 `editable_ai_result` 与约 3.45 GB 的 `manual_truth`。
- 状态加载已使用 `validate_label_ids=False`，没有在点击时对 3.45 GB 标注执行 `np.unique`；真实记录 profiling 中同步标签映射和状态恢复约 0.026 秒，标注角色不是本次卡顿根因。
- 正常 Windows GPU 路径原先仍把大 reslice 送入后台 CPU 降采样，生成约 431 MB 中间数组，耗时约 20 秒，完成上传时最大界面事件间隔约 176 ms。
- 同一真实文件直接使用既有 GPU compute 流式路径时约 0.52 秒完成，事件间隔明显更短。因此仅对“GPU + 具体 reslice + 无 ROI crop”优先使用 GPU 流式构建；普通大 Part 的后台策略保持不变。
- 切换时关闭上一个大型 memmap 原先同步占约 87 ms；现在旧数组交给后台释放，并在旧预览线程结束后再关闭，避免关闭仍在使用的映射。后台 CPU fallback 降采样也增加轻量解释器让出点，数值等价测试证明预览数组未改变。
- 最终真实 Windows GPU 复测：点击返回约 9 ms，GPU 预览约 0.48 秒完成，最大界面事件间隔约 69 ms，backend 为 `gpu_compute`。相关模块 304 条通过，最终九组验证更新为 **712 条全部通过**。

## Accepted 后续修复：带标注重切片侧栏检查不再扫描整卷

- 对同一真实 `GAGA-02-09 / roi_1` 再做未替换业务方法的函数级 profiling 后，确认先前“点击阶段没有标签扫描”的结论不完整：训练就绪状态已使用 `validate_label_ids=False`，但标签角色帮助文字仍会调用 AI 复核检查，并对约 3.45 GB 的 `editable_ai_result` 执行一次完整 `np.unique`。
- 这次同步扫描约耗时 13.0 秒，其中约 10.9 秒用于排序、1.2 秒用于展平大数组；重切片 TIFF 与两份标签映射本身合计仅几十毫秒。因此“带少量标注的这个 ROI 特别卡”实际来自侧栏提示，而不是图像、标注映射或 GPU 预览。
- 侧栏即时状态现在只检查文件、标签表和打开复核状态，并明确提示完整标签编号校验延后到核验操作；真正核验为训练真值时仍由后台 worker 执行严格全卷校验，未知标签编号仍会阻断，不改变 manual truth 安全边界。
- 新增 core 与 GUI 回归，明确禁止树选择路径调用 `validate_part_label_ids()`，并继续验证严格核验能够识别未知标签编号。
- 使用原项目 SQLite 记录和原始 sidecar 做只读复测，并屏蔽项目保存与实际三维绘制后，`load_part(GAGA-02-09, roi_1, reslice)` 的同步返回由约 13.35 秒降至约 24.6 ms；当前 `editable_ai_result` 显示层继续复用已打开的编辑映射，没有增加 3.45 GB 副本。
- 完整验证期间还发现删除当前 Part 仍调用第三轮已移除的 `_release_volume_array()`。现改用 `TifProjectLifecycleController` 统一停止预览并释放共享映射；相关删除回归恢复通过。
- 最终验证：项目/选择/标注/三维/生命周期 60 条通过，完整 `test_tif_workbench` 231 条通过；`py_compile` 与 `git diff --check` 通过。
