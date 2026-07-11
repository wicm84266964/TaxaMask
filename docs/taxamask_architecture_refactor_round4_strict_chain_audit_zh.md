# TaxaMask 第四轮拆分链路严格复核记录

日期：2026-07-12

状态：`completed / automation verified / researcher acceptance pending`

分支：`codex/taxamask-architecture-refactor-round4`

## 1. 复核目标

本次不是继续拆文件，而是反向检查拆分后的完整链路：项目与页面状态、Qt 信号、后台任务、图片与部位上下文、研究数据角色、测试 patch 点、Agent 上下文和退出保存。重点寻找“单个模块测试通过，但跨模块组合时可能串项目、串图片或串研究角色”的问题。

## 2. 结论

严格复核发现并修复了 4 类跨模块边界问题：SAM 结果缺少项目身份、后台图片导入完成回调缺少项目身份、Blink 子专家训练未进入项目切换锁且旧结果可能挂到新项目路由、进入 Start Center/Agent 后最近项目工作流类型可能丢失。另补齐了 parent training error 的旧项目回调检查。

这些问题都发生在“线程刚结束，但 Qt 回调尚未在界面线程落地”的极短窗口，不是算法、模型权重、SQLite schema 或标注格式错误。正常顺序操作通常不会触发，因此此前人工测试可以表现正常；一旦触发，影响的是结果归属和当前项目状态，所以仍按数据安全问题处理。

修复后完整 18 个 suite 共 1,149 条测试通过；1 条环境相关 TIF workbench 测试跳过，其余全部通过。架构指标保持 `main.py` 763 行、MainWindow 直接状态写入 0、直接 Qt 连接 0、真实连接 194。

## 3. 已修复问题

### 3.1 SAM 结果补齐项目身份

程序原来只记住 SAM 发起时的 image、part 和 description。如果在结果返回前切换项目，旧结果仍可能通过共享 `ProjectManager` 写入新项目。

现在 SAM prompt 同时保存项目管理器和规范化项目路径；项目切换在 `sam_busy` 期间会被阻止，结果回调再次核对项目身份。身份不匹配时只记录 stale event，不写 polygon、不安排保存。

研究意义：SAM 仍可在同一项目内写回发起提示的原图片，但不会把上一项目的蚂蚁部位掩码写进当前项目。

### 3.2 后台图片导入补齐完成回调保护

大批量导入线程直接持有发起时的项目对象。运行期间已有 busy gate，但线程结束与 queued success callback 执行之间存在极短窗口；旧回调可能在新项目中继承 crop provenance 并刷新列表。

现在 success/error 回调核对项目身份，finished 只清理自己拥有的进度框和线程引用；旧任务不能重新启用新任务的控件，也不能把旧 crop provenance 写入新项目。

研究意义：批量导入的图片写入、裁切来源和当前项目列表保持同一归属。

### 3.3 Blink 子专家训练纳入项目锁和路由归属检查

子专家训练原来没有进入 MainWindow 的项目 busy gate。训练器虽然使用启动时的项目路径生成数据和模型，但完成回调通过共享 Blink `ProjectManager` 自动登记 route candidate；若项目已切换，可能把旧项目训练结果挂到新项目的 parent-child route。

现在子训练运行时阻止切换项目；每个 result/report/error/cancelled/finished 回调绑定具体 worker，并比较 worker 的启动项目路径与当前项目路径。旧项目模型文件可以保留作训练产物审计，但不会刷新当前模型库、不会登记或启用当前项目 route，也不会清理新训练线程。

研究意义：例如旧项目的 `Head -> Mandible` 专家不会自动成为新项目同名路线的候选或指定模型。

### 3.4 Start Center / Agent 保留最近工作台类型

`active_project_kind` 同时承担当前页面模式；进入 Start Center 或 Agent 时会变为 `start`。此前 `_active_recent_project_path()` 在该状态下不能可靠区分最后使用的是 2D/STL 还是 TIF。

现在单独保存 `last_workbench_kind`。打开、创建或进入 2D/TIF 工作台时更新它；进入 Start Center/Agent 前记住原工作台。最近项目、退出保存和 Agent 项目标签可以继续定位正确的 TIF、普通 2D 或 STL rendered-view 项目。

### 3.5 Parent training error 补齐 stale guard

训练 success 和 finished 已检查 project context，但 error 回调此前没有。现在旧项目 error 只记录 stale event，不弹出当前项目失败提示，也不启动当前项目的 OOM 重试。

## 4. 信号与生命周期复核

- 架构扫描记录 194 条真实 `connect/connect_once`，精确重复连接 0。
- MainWindow 类体直接连接仍为 0；Blink、PDF、TIF 的固定 shell 信号继续由 `MainWindowSignalRouter.connect_once()` 管理。
- Blink 子训练共享进度信号仍按线程标记只连接一次；BlinkLab 自身回调改为捕获具体 worker，避免旧 finished 清理新 worker。
- VLM 继续同时检查 run id 与 project context；prediction、external batch、dataset export 和 autosave 继续检查启动项目。
- 预加载 SAM/parts model 属于全局运行时资源，不写项目研究数据，不需要绑定项目路径。

## 5. 研究数据角色复核

| 数据角色 | 严格复核结果 |
| --- | --- |
| 2D manual / confirmed polygon | 不被 prediction 或 VLM 覆盖；通过 |
| Model / VLM auto box 与 polygon | 保持 draft；未确认草稿被训练预检排除；通过 |
| Box-only AI draft | 不能直接进入训练；通过 |
| Blink trajectory | 仍是子专家训练数据，不等同 manual label；通过 |
| Blink trained expert | 旧项目模型可保留，但 route 只能写回匹配项目；通过 |
| PDF / STL provenance | 仍是来源证据，不自动成为训练真值；通过 |
| TIF editable AI / raw backup | 不自动提升为 `manual_truth`；通过 |
| TIF `manual_truth` | 训练只使用允许角色和已存在真值；通过 |

## 6. 测试真实对接复核

- Stage 3-8 contract tests继续断言 MainWindow 方法身份来自对应 workflow mixin。
- 新测试直接对接 `main_window_start_center.py`、`main_window_project_lifecycle.py`、`main_window_image_navigation.py`、`main_window_annotation.py`、`main_window_model_management.py`、`main_window_training.py` 和 `blink_lab.py`。
- 没有把新保护写回 `main.py`，也没有通过旧私有实现副本让测试假通过。
- 新增覆盖：最近 TIF 工作台恢复、旧图片导入回调、旧 SAM 结果、子训练/SAM busy gate、旧 parent training error、旧 Blink route result。

## 7. 自动化证据

- `scripts/run_validation_suite.py --timeout 180`：18 suites，1,149 tests，1 skip，其余通过。
- `taxamask_architecture_round4`：59 条通过。
- `blink_locator`：104 条通过。
- 数据角色定向回归：training preflight、VLM、TIF truth/label/write guard 全部通过。
- 架构扫描：763 / 36 / 13 行，MainWindow 状态写入 0、连接 0，总连接 194。
- 全目录 `compileall`、架构账本再生成、`git diff --check` 在最终提交前执行。

## 8. 仍需人工观察的边界

- 真实 SAM 推理期间尝试打开另一项目，应看到项目忙提示；同项目内切到另一图片后，结果仍应回到发起提示的图片。
- 真实 Blink 子专家训练期间尝试打开另一项目，应被阻止；训练结束后 route 应只出现在原项目。
- 从 TIF 或 STL 项目进入 Agent/Start Center 后正常退出并重开，最近项目应仍是原 TIF/STL 项目。
- 大型 TIF/GPU 预览、真实 VLM API 和真实训练性能仍依赖本机数据与硬件；本次没有修改这些算法路径。

## 9. 最终判断

拆分后的跨模块链路在自动化范围内已形成闭环：项目身份在任务启动、结果、错误、完成和项目切换处都有明确边界；研究数据角色和 194 条信号没有因修复而改变。当前没有发现未处理的高风险数据覆盖问题。

候选仍保持 `researcher acceptance pending`，不推送 GitHub、不合并 `main`、不创建新 Release。
