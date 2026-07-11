# TIF 工作台第三轮 Stage 10 真实研究流程验收卡

日期：2026-07-10

适用候选：第三轮架构整理自动门与隔离真实蚂蚁体积闭环通过后的工作树。

## 已由隔离真实数据证明

以下不需要在原始 289 GB 项目上重复做破坏性写入：

- 真实蚂蚁体积可加载到 2D/3D 工作台。
- 两个 specimen、part、reslice 可连续往返，SQLite 重开后选择恢复。
- 跨关键切片 contour 可生成 mask preview，并接受为 part mask。
- ROI-to-Part 可创建真实体积 part，bbox 和 accepted mask 非空。
- 部位 editable AI result 可编辑和手动保存，part mask 不被标注保存覆盖。
- 自动保存快照后同切片继续编辑会保留较新 revision/dirty，最终保存后新修改存在。
- 材料 3 可新增、跨切片写入、保存并 SQLite 重开；mask preview 可清除、修改关键切片后重建并接受。
- 旧 Preview 任务在切换 specimen 后被取消，不覆盖既有 cache 或当前选择。
- Truth Promotion 生成 manual truth 时 raw prediction backup 保持原路径与内容；外部 prediction 正确 shape 可导入、错误 shape 被拒绝且 manual truth 不变。
- 训练诊断在缺少 reslice record/image 时明确阻止样本；项目无登记模型时模型库保持空状态。
- Local Axis 三点/roll reference 可执行 reslice，image/metadata 和重开记录存在。
- 真实源 sidecar 在整个验收前后 SHA-256 树哈希一致。
- 当前离屏环境正常显示 CPU fallback 状态；真实切片、三栏布局和滚动区无明显空白或重叠。

## 操作前保护

- 优先使用可复制的小型项目或确认已有备份的真实项目，不在唯一原始项目上试验删除、覆盖或批量接受。
- 开始前记录项目路径、当前 specimen/part/reslice 和 Git 状态。
- 不移动或改名原始 TIF。
- 训练/预测先使用小样本和短运行；不要直接启动长时间全量任务。

## A. 可见窗口选择与 Preview

1. 打开真实项目，选择一个有 part/reslice 的 specimen。
2. 在 specimen A → part → reslice → specimen B → specimen A/reslice 之间连续切换 3 次。
3. 在 3D preview 正在构建时切换到另一个 specimen。

通过标准：

- 树选中项、2D 切片、状态栏和 3D source 始终属于同一目标。
- 旧 preview 完成后不把界面跳回旧 specimen。
- 无空白画布、重复弹窗或按钮触发两次。

失败意义：Selection context 或 stale preview guard 仍有真实时序缺口；不要继续保存或训练。

## B. 自动保存与同切片继续编辑

1. 在 working edit 或 editable AI result 上连续编辑至少 3 个切片。
2. 等待自动保存开始，保存过程中继续修改其中一个已编辑切片。
3. 自动保存结束后执行手动保存，关闭并重开项目。

通过标准：

- 后续修改仍保持 dirty，不能被较早的自动保存完成事件清掉。
- 重开后所有预期标注仍存在。
- 保存失败时仍显示未保存状态，并可再次保存。

失败意义：会有标注丢失风险，应停止大规模人工标注。

## C. Material 与 Mask 视觉边界

1. 在隔离 part 中新增一个材料标签并跨 2–3 个切片编辑。
2. 构建 mask preview，随后取消；修改关键切片后重建并接受。
3. 保存并重开，核对 material 名称、颜色、mask 边界和 accepted 状态。

通过标准：

- preview、accepted mask 和 editable label 是三个清晰状态。
- 取消 preview 不删除已接受 mask。
- 保存标注不覆盖 part mask；删除材料时已使用材料受到保护。

失败意义：材料语义或 accepted mask 可能混淆，影响训练标签可信度。

## D. GPU 与交互质量

1. 在 Windows 可见窗口打开同一个真实体积，查看状态栏 renderer。
2. 若显示 GPU ray march，拖动旋转、滚轮缩放、quality、cutoff 和 ROI scale。
3. 若显示 CPU fallback，确认原因提示可理解，并检查 2D 标注仍可继续。
4. 查看 source、mask、ROI 和 Local Axis overlay。

通过标准：

- 拖动时可降质量，释放后恢复高质量。
- GPU 失败时回退到 CPU，不崩溃、不把资源不足误报为数据损坏。
- overlay 与当前 specimen/part/reslice 一致。

失败意义：属于 GPU 驱动/renderer 或真实交互性能问题，不代表原始 TIF 损坏。

## E. Local Axis 主观方向

1. 在真实 part 上用界面点选三点和侧参考点。
2. 观察轴线、参考平面和 roll 方向是否符合蚂蚁部位的解剖方向。
3. 执行重切片，切换到其他 part 等待任务结束，再返回查看结果。

通过标准：

- 三点角色和侧参考没有颠倒。
- 旧任务不抢焦点；生成 reslice 记录可重开。
- 切片方向对分类研究具有可解释性。

失败意义：数学链可能可运行，但点位角色或界面提示不符合研究语义，需要停止批量 reslice。

## F. 训练、预测与结果复核

已完成的客观证据：Dataset601 匹配真实脑体积已在 GPU 0 上完成 nnU-Net 预测，结果安全进入待复核层；SQLite 重开后 working edit、raw backup 和 model draft 均可追溯。以下步骤主要用于研究者判断结果来源、脑区边界合理性和真实训练操作体验。

1. 查看训练样本诊断和模型库，确认排除原因与实际标签状态一致。
2. 用小样本启动 prepare/train/predict，观察进度、取消、失败日志和 run folder。
3. 比较 manual truth 与 editable AI result，接受一组 AI 结果。
4. 导入一份外部 prediction TIF，分别尝试正确 shape 和错误 shape/context。
5. 后台任务运行时切换 specimen/part/reslice。

通过标准：

- 只有 train-ready 样本进入训练。
- AI 接受经过 truth promotion，raw prediction 保留审计副本。
- 外部 prediction 不覆盖 manual truth；错误 shape/context 被明确拒绝。
- 旧后台结果不刷新或写入新目标。

失败意义：可能影响训练数据来源可信度或把结果写入错误个体，应立即停止训练/批量接受。

## 验收记录

| 分组 | 结果 | 使用项目/目标 | 备注 |
| --- | --- | --- | --- |
| A 选择与 Preview | 客观技术链通过；待用户主观确认焦点/操作感受 | 隔离真实头部 + Dataset601 | 状态、画布、目标和 stale guard 已验证 |
| B 自动保存 | 自动与真实数据通过；待肉眼核对提示 | 隔离 22-38/part_1 | revision/dirty/重开已验证 |
| C Material/Mask | 自动与真实数据通过；待肉眼核对边界 | 隔离 22-38/part_1 | 新增/跨切片/preview 重建/接受/重开已验证 |
| D GPU/交互 | CPU 3D fallback 与 overlay 可见技术项通过；OpenGL 交互未验收 | 隔离真实头部 | 本机 OpenGL 初始化兼容性单列，不视为数据损坏 |
| E Local Axis 方向 | 通过（用户确认） | 真实 24-43 头部隔离副本 | 输出 Z、Roll A/B、平面 C 符合解剖方向 |
| F 训练/预测/结果 | 通过（用户确认脑区边界合理） | Dataset601 匹配脑体积隔离项目 | working edit 保持 pending review；raw backup 重开；未自动写 manual truth |

全部通过后，可将 Stage 10 状态改为 `accepted`，再决定是否同步根目录 `CHANGELOG_zh.md` 和 `LLM_CONTEXT_DETAILED.md`。

## 2026-07-10 可见窗口技术预检结果

已使用 `.tmp_validation/round3_manual_acceptance/启动第三轮可见验收.bat` 在隔离真实项目完成技术预检：

- 下拉框显示“三维体预览”，内部 `display_mode=volume`，实际 `view_stack` 当前页为 volume canvas。
- “正在加载选中的部位体数据与标签……”不再滞留；进入三维后显示只读降采样与 renderer 回退说明。
- 真实 24-43 头部三维体、mask 内图像、输出 Z、Roll A/B、平面 C 和三维 overlay 均可见。
- 本机 OpenGL 初始化不稳定，隔离验收入口使用项目正式支持的 CPU 3D fallback；这不会写入原始 TIF，也不会改变 Local Axis 数学或标注数据。
- 技术状态记录：`.tmp_validation/round3_manual_acceptance/visible_state_after_fix.json`。
- 可见截图：`.tmp_validation/round3_manual_acceptance/visible_window_after_state_fix.png`。

因此 D 节的“renderer 失败可安全回退、overlay 与当前部位一致”技术项已通过。仍需用户完成两项科研判断：

1. 当前输出 Z、A/B/C 是否符合蚂蚁头部的真实解剖方向。
2. 切换到 `dataset601-gpu-result` 后，17 类脑区结果是否具有科研合理性。

## Dataset601 可见结果证据

- 一键入口：`.tmp_validation/round3_manual_acceptance/启动Dataset601脑区结果验收.bat`。
- 来源与角色状态：`.tmp_validation/round3_manual_acceptance/visible_brain_state.json`。
- 三维源体截图：`.tmp_validation/round3_manual_acceptance/visible_brain_result.png`。
- 中间 Z 切片 working edit 彩色叠加状态：`.tmp_validation/round3_manual_acceptance/visible_brain_overlay_state.json`。
- 中间 Z 切片彩色 prediction overlay：`.tmp_validation/round3_manual_acceptance/visible_brain_prediction_overlay.png`。
- 客观状态为：17 个标签值、working edit = `pending_review`、raw backup = `raw_backup`、manual truth 不存在，因此当前结果不可自动 promotion。
- 训练诊断曾在 manual truth 缺失时额外误报 `image_label_shape_mismatch`；实际 image、working edit、raw backup shape 均为 647×647×195。现已修复为只有两侧体数据都存在时才报告 shape mismatch，并去除重复 `manual_truth_missing`。
