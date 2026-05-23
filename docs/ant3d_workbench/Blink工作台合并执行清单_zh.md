# Blink 工作台合并执行清单

日期：2026-05-22

对应设计文档：

```text
docs/ant3d_workbench/Blink工作台合并设计方案_zh.md
```

合并前本地 git 基线：

```text
pre-blink-workbench-merge
```

本清单用于长任务实施时逐项推进和复核。每个阶段完成后应运行相应测试，并确认研究流程没有被破坏。

## 阶段 0：实施前确认

- [x] 确认当前工作区干净。
- [x] 确认 `pre-blink-workbench-merge` tag 存在。
- [x] 阅读 `Blink工作台合并设计方案_zh.md`。
- [x] 阅读当前 Blink 入口逻辑：
  - `AntSleap/main.py::launch_blink_from_workbench`
  - `AntSleap/main.py::_collect_blink_roi_candidates`
  - `AntSleap/ui/blink_lab.py::start_session`
  - `AntSleap/ui/blink_lab.py::run_auto_annotate`
  - `AntSleap/ui/blink_lab.py::run_auto_shrink`
  - `AntSleap/ui/blink_lab.py::train_expert_model`
- [x] 明确第一轮只做主工作台吸收 Blink 能力，不删除 Blink 后端。

## 阶段 1：父子关系状态模型

- [x] 在主工作台中新增当前父子上下文计算方法。
- [x] 父部位候选默认读取项目的 locator scope / 主定位器部位。
- [x] 子部位默认识别为不在父部位候选池中的部位。
- [x] 子部位父级解析优先级：
  - 项目记忆的 `child -> parent`
  - 部位树层级
  - 可用父部位候选
  - 用户手动指定
- [x] 复用或扩展 `blink_context_roi_parents` 作为项目记忆。
- [x] 选中部位时更新：
  - 当前部位
  - 部位角色
  - 父级上下文
  - 当前路由
  - 父级框存在状态
  - 路由专家状态
- [x] 无父级或无父级框时禁用父子精修按钮。

## 阶段 2：右侧父子精修 UI

- [x] 在主工作台右侧 AI 区下方新增“父子精修 / Blink”小区。
- [x] 显示当前路由，例如 `Head -> Mandible`。
- [x] 显示父级框状态：已存在 / 未框选。
- [x] 显示路由专家状态：已指定 / 未指定 / 路由禁用。
- [x] 加入“配置路由专家”按钮。
- [x] “配置路由专家”按钮行为：
  - 打开设置中的路由专家配置；
  - 定位到当前 `parent -> child`；
  - 当前路由不存在时创建候选路由或提示创建；
  - 当前上下文无效时置灰并提示原因。
- [x] 在画布上方加入框工具：
  - 正式标注框
  - 收缩松框
- [x] 加入操作按钮：
  - 自动标注子部位
  - 执行自动收缩
  - 训练当前子部位专家
- [x] 确保该小区视觉上和全图 AI 工作流区分开。

## 阶段 3：框选工具角色化

- [x] 明确现有框选工具在主工作台中的行为。
- [x] 当前选中父部位时：
  - 框选工具画父级上下文框；
  - 默认锁定父部位长宽比。
- [x] 当前选中子部位且顶部工具为“正式标注框”时：
  - 框选工具画子部位正式标注框；
  - 不继承父部位固定比例。
- [x] 当前选中子部位且顶部工具为“收缩松框”时：
  - 框选工具画 shrink loose box；
  - 不覆盖正式标注框；
  - 用于自动收缩 trajectory。
- [x] SAM prompt box 继续作为临时提示框，不写入正式框角色。
- [x] UI 在画布上方明确提示当前框工具。
- [x] 数据层区分：
  - `parent_context_box`
  - `child_annotation_box`
  - `shrink_loose_box`
  - `sam_prompt_box`

## 阶段 4：固定长宽比父级框

- [x] 设计父级框比例配置结构。
- [x] 默认比例建议：
  - `Head`: `1:1`
  - `Mesosoma`: `4:3`
  - `Gaster`: `4:3` 或 `3:2`
  - `Whole body`: `16:9`
- [x] 当前父部位没有配置时使用保守默认比例。
- [x] 支持项目或全局设置中调整比例。
- [x] 父部位框绘制时默认锁定比例。
- [x] 支持临时解除比例锁定。
- [x] 子部位框和收缩松框不使用父部位比例。
- [x] 测试不同图像尺寸下框比例稳定。

## 阶段 5：主工作台内自动标注子部位

- [x] 将 Blink `run_auto_annotate` 的核心能力接入主工作台。
- [x] 输入来自主工作台当前上下文：
  - 当前图像
  - 当前子部位
  - 当前父部位
  - 当前父级框
  - 当前项目 route manifest
- [x] 调用 route-appointed expert 推理当前子部位。
- [x] 推理得到的 box 可作为子部位候选框或 SAM prompt。
- [x] 生成草稿 polygon 后直接显示在主画布。
- [x] 明确草稿是否立即保存，或是否需要用户确认。
- [x] 无路由专家时提示并引导点击“配置路由专家”。
- [x] 不再要求进入 Blink session。

## 阶段 6：主工作台内自动收缩

- [x] 将 Blink `run_auto_shrink` 核心能力接入主工作台。
- [x] 自动收缩前检查：
  - 当前选中子部位；
  - 当前父级上下文有效；
  - 父级框存在；
  - 子部位黄金 polygon 存在；
  - 收缩松框存在；
  - SAM / parts model 可用。
- [x] 使用收缩松框和黄金 polygon 生成 trajectory。
- [x] trajectory 保存到项目，并记录 parent context。
- [x] 自动收缩完成后更新主画布。
- [x] 不再需要用户点击 Apply to Global。
- [x] 失败时给出研究者可理解的提示。

## 阶段 7：训练当前子部位专家

- [x] 将 Blink `train_expert_model` 的入口接入主工作台右侧小区。
- [x] 训练按钮只负责当前子部位专家训练。
- [x] 训练参数继续来自设置中的 Blink 训练设置。
- [x] 训练上下文必须包含：
  - 当前父部位
  - 当前子部位
  - 当前项目路径
  - 当前 route manifest
  - 已保存 trajectory 数据
- [x] 训练完成后继续注册 route candidate。
- [x] 如果当前路由没有指定专家，可按既有规则自动指定或作为候选。
- [x] 训练结果应能在设置中的路由专家配置里看到。
- [x] 主工作台只显示路由专家状态，不显示完整专家列表。

## 阶段 8：设置入口和路由专家配置联动

- [x] 路由专家配置面板支持从主工作台传入目标路由。
- [x] 打开配置时自动定位到当前 `parent -> child`。
- [x] 当前路由不存在时支持创建候选路由。
- [x] 配置面板关闭或保存后刷新主工作台路由状态。
- [x] 保持路由专家候选、启用、删除、备注管理仍在设置中完成。

## 阶段 9：隐藏独立 Blink 日常入口

- [x] 主工作台流程稳定后隐藏 `Open in Blink Workbench` 按钮。
- [x] 从日常 tab 中移除或隐藏独立 Blink Workbench。
- [x] 保留旧 Blink widget 作为内部兼容或开发回退，直到测试覆盖足够。
- [x] 移除或禁用 Blink 空格快捷键展示逻辑。
- [x] 确认主工作台不再依赖 `tabs.setCurrentWidget(self.blink_lab)` 完成小部位标注。

## 阶段 10：测试与复核

- [x] 更新 GUI smoke tests。
- [x] 新增或调整父子上下文测试：
  - 父部位识别；
  - 子部位识别；
  - 父级记忆；
  - 路由状态显示。
- [x] 新增框角色测试：
  - 父部位固定比例框；
  - 子部位自由框；
  - 收缩松框不覆盖正式框；
  - SAM prompt 不写入正式框。
- [x] 新增自动标注测试：
  - 有路由专家；
  - 无路由专家；
  - 无父级框。
- [x] 新增自动收缩测试：
  - 缺 polygon；
  - 缺 loose box；
  - trajectory 带 parent context。
- [x] 新增训练入口测试：
  - 使用当前路由；
  - 训练后 route candidate 更新；
  - 设置面板可见。
- [x] 运行：
  - `python -m py_compile AntSleap/main.py AntSleap/ui/blink_lab.py`
  - `python -m unittest tests.test_gui_smoke`
  - 相关 Blink / project / route 单元测试。

## 阶段 11：人工验收场景

> 状态：待真实 2D/STL 项目人工验收。自动化测试已覆盖这些路径的接口和数据写入，但不能替代研究者用真实图像、真实专家模型和真实 trajectory 进行质量判断。

- [ ] 打开 2D/STL 项目。
- [ ] 选择父部位 `Head`。
- [ ] 用框选工具画 Head 框，确认默认锁定比例。
- [ ] 选择子部位 `Mandible`。
- [ ] 右侧显示 `Head -> Mandible`。
- [ ] 子部位正式框自由绘制，不受 Head 比例限制。
- [ ] 在画布上方切换到收缩松框，画一个松框。
- [ ] 画或确认 Mandible polygon。
- [ ] 执行自动收缩，确认 trajectory 保存。
- [ ] 点击训练当前子部位专家。
- [ ] 进入配置路由专家，确认定位到 `Head -> Mandible`。
- [ ] 指定或查看专家后返回主工作台。
- [ ] 执行自动标注子部位。
- [ ] 确认不需要打开独立 Blink 工作台。

## 阶段 12：文档同步

- [x] 合并稳定后更新 `TaxaMask使用手册.md`。
- [x] 合并稳定后更新 `README.md` 中 2D/STL 工作流描述。
- [x] 重大行为变化接受后，再同步 `CHANGELOG_zh.md`。
- [x] 重大行为变化接受后，再同步 `LLM_CONTEXT_DETAILED.md`。
- [x] 更新 `.lab-agent/skills/taxamask-workflows/SKILL.md` 中的 Blink/2D 工作流说明。

## 完成定义

本任务完成时应满足：

- 研究者在主标注工作台即可完成小部位父子精修；
- 独立 Blink Workbench 不再是日常必要入口；
- 父部位固定比例框工作稳定；
- 子部位框和收缩松框语义清楚；
- 自动标注、自动收缩、专家训练都能使用当前父子上下文；
- 路由专家配置有主界面快速入口；
- 旧项目和已有 2D/STL 标注流程不被破坏；
- 自动化测试通过，人工验收清单留待真实项目确认。


## 实施复核记录（2026-05-22）

本轮已完成主标注工作台吸收 Blink 日常能力的第一轮实现。独立 Blink widget 和旧入口函数保留为兼容回退，但 2D/STL 日常 tab 不再显示独立 Blink Workbench，顶部旧入口按钮也已隐藏。

已完成的自动化复核：

- `python -m py_compile AntSleap/main.py AntSleap/ui/canvas.py AntSleap/core/project.py AntSleap/ui/blink_lab.py`
- `python -m unittest tests.test_gui_smoke`
- `python -m unittest tests.test_ui_polish_scope`
- `python -m unittest tests.test_blink_bridge tests.test_part_tree tests.test_locator_scope`

实现说明：

- `parent_context_box` 和 `child_annotation_box` 继续复用项目原有 manual boxes 字段，通过当前部位角色区分语义。
- `shrink_loose_box` 使用新增 `shrink_loose_boxes` 字段保存，避免覆盖正式子部位标注框。
- `sam_prompt_box` 仍只走原有 SAM prompt 流程，不写入正式框角色。
- 训练入口复用现有 Blink 训练线程和 route candidate 注册逻辑，避免重写训练后端。
- 父部位固定比例框支持设置面板调整，并在主工作台提供临时解除比例锁定。

待人工验收重点：

- 在真实 2D/STL 项目中确认 Head 等父部位标注框默认比例符合实际图像视角。
- 在已有 route expert 的项目中确认“自动标注子部位”输出框和草稿 polygon 的质量。
- 用真实收缩松框和子部位 polygon 确认 trajectory 保存内容能被 Blink 训练继续消费。

文档同步状态：

- 已更新 `TaxaMask使用手册.md`：独立 Blink 日常流程改为主工作台父子精修流程。
- 已更新 `README.md`：2D/STL 入口改为 Labeling Workbench 内集成 Blink refinement。
- 已更新 `CHANGELOG_zh.md`：新增 2026-05-22 主标注工作台吸收 Blink 父子精修记录。
- 已更新 `LLM_CONTEXT_DETAILED.md`：同步 v3.25 当前架构语义。
- 已更新 `.lab-agent/skills/taxamask-workflows/SKILL.md`：Agent 工作流卡片同步新边界。
