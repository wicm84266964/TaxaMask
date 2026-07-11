# TIF 工作台架构整理第三轮 Stage 1 正式复核记录

日期：2026-07-10

状态：`accepted`

需求文档：`docs/tif_workbench_architecture_refactor_round3_requirements_zh.md`

执行清单：`docs/tif_workbench_architecture_refactor_round3_execution_checklist_zh.md`

## 完整工作流边界

Stage 1 只负责工作台启动装配、最小 View contract、信号登记和销毁顺序，不负责 Annotation、ROI、Part Mask、Preview、Local Axis 或训练业务决策。Shell 创建 service/controller，View 按 scope 暴露已登记控件，Signal Router 保证同一 scope/key 幂等绑定和可解绑。

## 实施与正式修正

- `TifWorkbenchShell` 分开 foundation、runtime defaults、startup finalize、signal bind 和 shutdown。
- 建立稳定 controller registry，顺序为 Selection、Lifecycle、Annotation、ROI、Part Mask、Preview、Volume、Local Axis、Backend。
- 增加通用 lifecycle hook 广播：`on_project_opened`、`on_selection_changed` 可按需调用；shutdown 固定先 `on_workbench_closing`、再解绑、最后 `on_workbench_destroyed`。
- `TifWorkbenchView.require(scope, name)` 对未登记控件直接报错，避免 controller 隐式读取任意控件。
- 删除 Widget 重复的 `release_volume_renderer`，真实关闭事件直接调用 Volume controller，避免 Shell/Widget/Volume 三处拥有同一生命周期责任。
- 顶层 Start Center、Ask Agent、Show Log 三条低风险信号由 Shell scope 管理；高风险信号留给对应工作流阶段。

## 信号与生命周期合同

- 相同 signal/slot 重复 bind 返回 false，不重复连接。
- 同一 scope/key 更换 slot 时先断开旧连接。
- `unbind_scope` 与 `unbind_all` 会停止后续 delivery。
- controller registry 和 lifecycle hook 有直接测试；未实现某 hook 的 controller 不受影响。
- Shell shutdown 后 Signal Router connection count 为 0。

## 指标

| 指标 | Stage 0 正式结束 | Stage 1 正式结束 |
| --- | ---: | ---: |
| 主文件物理行数 | 8,574 | 8,566 |
| Widget 方法数 | 417 | 416 |
| 4 行以内方法 | 150 | 150 |
| 主文件 `.connect(...)` | 114 | 114 |
| 私有测试引用次数 | 410 | 410 |

Stage 1 的主要价值是建立可审计装配和生命周期 contract，不以大幅减行作为完成标准。

## 自动门

- Shell/View/Router 窄测试：6 条通过。
- `tif_workbench`：245 条通过。
- `tif_layout`：5 条通过。
- `tif_architecture_round3`：2 条通过。
- `gui_smoke`：94 条通过。
- `ui_polish`：83 条通过。
- 相关文件 `py_compile` 通过。
- `git diff --check` 无空白错误，仅 LF/CRLF 提示。

## 研究门

Stage 1 不写 TIF、mask、truth、prediction、reslice 或训练结果。GUI smoke/UI polish 已证明 objectName、页面、翻译和基础启动没有回退；真实研究数据验收不属于本阶段。

## 对照需求文档

- 装配、布局、信号和 controller registry 已分离，方向符合 Shell/View/Signal Router 目标。
- View contract 限制控件访问；controller 仍可持有 Widget 作为阶段性数据/命令适配，但各工作流必须在 Stage 2-9 继续减少任意访问，不能以本阶段为永久豁免。
- Shell 暂存的多工作流默认字段必须随状态迁移逐阶段退出，不能演化成新的状态巨型对象。
- 未修改数据格式、训练算法、Local Axis 数学或 GPU renderer 数学。

## 阶段结论

Stage 1 自动门和需求方向复核通过，记为 `accepted`，进入 Stage 2：Selection 与 Project Lifecycle。
