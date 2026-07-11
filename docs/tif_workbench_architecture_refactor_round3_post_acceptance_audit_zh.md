# TIF 工作台第三轮优化验收后审计

日期：2026-07-11

状态：`completed`

审计范围：第三轮架构拆分后的工作流边界、Qt 信号、异步任务、数据角色、失败恢复、性能回归、测试结构和长期维护风险。

## 结论

第三轮优化已经达到可继续用于蚂蚁 TIF/CT 研究工作的稳定候选状态。本次审计没有发现仍未修复的严重数据覆盖风险；原始 TIF、working edit、manual truth、raw prediction backup、accepted mask 和 Local Axis reslice 的角色边界均有自动化证据。

但“主文件显著缩小”不等于“完全解耦”。当前架构仍是过渡形态：多数 controller 持有完整 `TifWorkbenchWidget`，Selection 生命周期事件框架没有形成生产 controller 的订阅闭环，两个 controller 已超过第三轮自定规模复核线，测试仍大量依赖 Widget 私有实现。这些问题不会直接改变当前标注结果，但会提高下一次功能修改时引入状态错位、重复刷新或陈旧回调的概率。

本次审计额外修复了两个用户可见问题：

1. 大型已保存重切片不再在选择回调中同步建立 GPU 纹理，避免 `GAGA-02-09` 这类 1.7 GB 重切片短暂无响应。
2. 后端任务在线程仍活跃但 task id 缺失时，失败摘要不再为空；无活动线程的旧失败回调仍不能覆盖当前选择状态。

## 当前量化状态

架构分析脚本：`scripts/analyze_tif_workbench_architecture.py`

| 指标 | 发布基线 | 当前 | 结论 |
| --- | ---: | ---: | --- |
| `tif_workbench.py` 物理行数 | 14,234 | 5,041 | 达标 |
| Widget 方法数 | 约 664 | 219 | 达标 |
| 4 行以内薄方法 | 约 147 | 39 | 达标，但不代表全部 wrapper 已退场 |
| 主文件直接 `.connect()` | 约 251 | 11 | 达标 |
| 测试总数（分析脚本口径） | - | 409 | 覆盖显著增加 |
| 直接引用私有实现的测试 | - | 140 | 仍是中风险债务 |
| 私有引用出现次数 | - | 377 | 仍是中风险债务 |
| 私有引用种类 | - | 57 | 仍是中风险债务 |

Controller 规模和完整 Widget 引用审计：

| Controller | 行数 | Widget 引用次数 | 审计判断 |
| --- | ---: | ---: | --- |
| Annotation | 1,208 | 347 | 可接受过渡状态 |
| Backend Panel | 1,343 | 416 | 接近复核线 |
| Local Axis | 1,354 | 281 | 接近复核线 |
| Part Mask | 1,708 | 635 | 超过 1,500 行建议线 |
| Volume Render | 2,675 | 563 | 接近 3,000 行硬上限，优先拆分 |
| Result Review | 695 | 190 | 可接受 |
| ROI | 745 | 229 | 可接受 |
| Selection | 142 | 36 | 边界较清晰 |
| Project Lifecycle | 181 | 53 | 边界较清晰 |

## 本次已修复风险

### 1. 陈旧异步回调写入当前上下文

已统一收紧 task context 匹配：空 specimen/part/reslice 不再作为通配符。Import、truth promotion、ROI、materialize、Backend、Volume Preview、Local Axis、Part Mask 和保存回调在更新当前界面或研究状态前检查任务上下文。

研究意义：研究者切换到另一只个体、部位或重切片后，旧任务不会把新选择刷新回旧目标，也不会把旧失败误标成当前编辑失败。

### 2. 大标签体在选择时全量扫描

部位或重切片选择不再执行严格标签编号全量扫描。严格 `np.unique` 验证保留在“接受为训练真值”等真正需要阻止错误标签进入训练的步骤。

真实 `GAGA-02-09` 证据：约 3.29 GB 标签体不再在选择阶段扫描；只读选择 profiling 从约 13.35 秒降到毫秒级挂载，标签安全检查没有被删除，只是移动到正确的验收边界。

### 3. 大型重切片同步 GPU 预览

真实重切片形状为 `765 x 1577 x 1428`，图像源约 1.72 GB。内存映射本身只需约 1-2 ms，卡顿来自选择完成后同步建立 GPU 纹理。当前大型重切片会先进入后台 preview build，再在界面线程上传已准备的预览。

研究意义：预览仍需要准备时间，但左侧树、状态区和窗口不应进入“未响应”；原始图像和两份标签不发生改写。

### 4. 后端失败提示被 task id 过滤为空

失败回调现在区分三种情况：

- task id 与当前上下文匹配：更新当前状态。
- task id 缺失，但当前后端线程仍活跃：显示失败摘要和日志入口。
- task id 缺失且没有活动线程：只保留后端运行区证据，不覆盖当前选择状态。

研究意义：训练失败时仍能看到“样本不足”或 nnU-Net 命令失败原因，同时旧回调不能干扰当前标注。

### 5. 后台任务取消和数组释放

Part Mask 取消会使 token 失效、取消 task，并在线程真正结束后清理引用。切换体数据时旧 memmap 在后台关闭；若旧 preview 仍使用映射，释放线程会等待 preview 结束。

研究意义：减少永久 busy lock、界面卡顿和 use-after-close 风险。

### 6. SQLite 与 sidecar 事务恢复

本轮补齐并验证了以下失败恢复：

- materialize 失败恢复 specimen 和旧 import report，并只删除本次新建 sidecar。
- sidecar role 更新先写临时副本，成功后替换目标。
- 材料表 JSON 损坏时拒绝用空材料覆盖 SQLite 上次有效值。
- 外部预测导入在 SQLite 失败时恢复 editable result、raw backup、draft 和 specimen 记录。
- Part 删除和 specimen scaffold 删除在 SQLite 失败时恢复记录、关联 ROI 和目录。
- 单个及批量 manual truth 提升在 SQLite 失败时恢复旧 truth sidecar 和项目记录。

研究意义：数据库写入失败不会留下“文件已变、项目记录没变”或相反的半完成状态。

## 剩余风险分级

### 中风险 R1：Controller 仍依赖完整 Widget

所有主要 controller 构造函数仍接收完整 `TifWorkbenchWidget`，运行时大量访问其字段和私有方法。`TifWorkbenchView.require()` 目前主要约束信号绑定，不约束 controller 的全部运行时访问。

影响：修改 Widget 字段名、初始化顺序或刷新顺序时，多个 controller 可能同时受影响；静态“方法存在”测试无法证明责任边界正确。

建议：第四轮先定义 Selection、Annotation、Preview 三个最小 port/protocol，不要一次替换全部 controller。

### 中风险 R2：生命周期事件框架没有生产订阅闭环

Shell 可以派发 `on_selection_changing`、`on_selection_changed`、`on_workbench_closing` 等 hook，但生产 controller 当前没有实现这些 hook。实际刷新仍主要由 `load_specimen()` / `load_part()` 手工按顺序调用。

影响：新增工作流时容易漏掉某个缓存、状态或控件刷新；事件框架测试证明了“能派发”，没有证明生产工作流“已订阅”。

建议：第四轮先迁移只读刷新，例如 Result Review cache、Preview owner 和 Local Axis summary；未保存确认仍保留 Coordinator 串行控制。

### 中风险 R3：Volume Render 和 Part Mask 正在形成第二个大类

`TifVolumeRenderController` 为 2,675 行，混合请求策略、缓存、GPU gateway、CPU fallback、交互状态和用户提示。`TifPartMaskWorkflowController` 为 1,708 行，混合材料表、关键切片、mask preview、接受和 materialize。

影响：主 Widget 虽然缩小，但复杂度可能只是转移；预览性能修复容易同时碰到 GPU、缓存和状态提示。

建议：只按稳定责任拆分，不按 helper 拆分。Volume Render 优先拆为 preview request/cache、GPU canvas gateway、CPU fallback/pixmap；Part Mask 优先拆为 material editor、preview lifecycle、accepted-mask commit。

### 中风险 R4：测试仍与私有实现强耦合

140 条测试包含 377 次私有引用。大量测试直接修改 Widget/controller 私有字段，容易在等价重构时产生高迁移成本，也可能跳过真实信号入口。

影响：测试全绿可以证明当前实现没有回退，但不能充分证明公共工作流契约稳定。

建议：第四轮设置逐步下降门槛，例如每阶段至少减少 15% 私有引用，并为 Selection、Annotation、Preview 建立公共 command/state fixture。

### 低风险 R5：动态 Qt 信号仍有少量直接连接

主文件仍有 11 处直接 `.connect()`，主要是动态 GPU canvas 和 import worker 生命周期；controller 内 worker/thread 信号也直接连接。它们有明确动态对象生命周期理由，但 signal router 无法统一审计这些连接。

建议：不必为了数字强制迁移 worker 信号；应为每类动态连接保留 cleanup/idempotence 测试，并在代码中保持 owner 明确。

### 低风险 R6：真实性能证据仍依赖本机 fixture

当前有大型重切片后台策略测试和真实 GAGA profiling，但没有跨机器稳定的毫秒阈值。磁盘缓存、显卡驱动和 OpenGL 后端会显著影响绝对时间。

建议：自动化只验证“不在选择回调执行全量扫描/同步大预览”和后台策略；绝对延迟继续用真实项目人工验收，避免脆弱的硬件时间断言。

## 数据安全审计结论

| 研究资产 | 当前保护 | 审计结论 |
| --- | --- | --- |
| 原始 TIF | 导入和 materialize 不删除来源；失败只清理本次新建文件 | 通过 |
| working edit / editable result | 保存失败保留 dirty；预测导入事务恢复 | 通过 |
| manual truth | 只能显式提升；预测不直写；失败恢复旧 sidecar | 通过 |
| raw prediction backup | 只读审计角色；不能提升为 truth | 通过 |
| accepted mask | preview 与 accepted 状态分离；取消/失败不自动提交 | 通过 |
| Local Axis reslice | 只读已保存重切片；旧任务不能抢回当前选择 | 通过 |
| SQLite 项目索引 | 删除、导入、提升和材料损坏均有回滚/拒绝覆盖证据 | 通过 |

## 自动化验证证据

最终套件清单共 777 条，1 条按本机环境跳过，其余通过：

| Suite | 数量 | 结果 |
| --- | ---: | --- |
| `tif_core` | 90 | 通过 |
| `tif_storage_safety` | 16 | 通过 |
| `tif_services` | 25 | 通过 |
| `tif_preview_export` | 108 | 通过 |
| `tif_model_backends` | 31 | 通过 |
| `tif_workbench` | 317 | 通过，1 skip |
| `tif_layout` | 5 | 通过 |
| `tif_architecture_round3` | 4 | 通过 |
| `gui_smoke` | 94 | 通过 |
| `ui_polish` | 83 | 通过 |
| `validation_tooling` | 4 | 通过 |

补充静态证据：

- extracted controller 调用缺失 Widget 方法：0。
- Widget 调用缺失 self/controller 方法：0。
- controller 把 `self` 误作 `QMessageBox` parent：0。
- signal router 重复绑定和 unbind 合同通过。
- `py_compile` 和 `git diff --check` 通过。

## 人工与真实数据证据

- 用户已确认真实蚂蚁头部 Local Axis 解剖方向合理。
- 用户已确认 Dataset601 脑区边界合理。
- 标签表绑定重开恢复、三维体预览、GPU failure 回退、旋转交互已完成手工回归。
- `GAGA-02-09` 大型重切片已确认包含大体积 editable/manual 标签；本次优化只改变预览调度，不改变标签内容。

这些证据支持蚂蚁领域当前工作流，不构成跨类群或跨硬件的普适验证。

## 第四轮建议边界

第四轮不建议再次以“主文件降行数”为目标。优先级应为：

1. 建立最小 Workbench ports，降低 controller 对完整 Widget 的访问。
2. 让只读工作流真正订阅 Selection 生命周期事件，减少手工刷新清单。
3. 拆分 Volume Render 和 Part Mask 两个超线 controller。
4. 逐步迁移私有测试到公共 command/state 契约，并设置可量化下降门槛。
5. 保留数据格式、训练算法、Local Axis 数学和 renderer 数学不变，除非另开需求。

在开始第四轮前，应先提交或建立一个本地 Git 里程碑，确保第三轮 accepted 状态可恢复。当前工作树改动规模很大，不适合继续叠加另一轮广泛迁移而没有里程碑。
