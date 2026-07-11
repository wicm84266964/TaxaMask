# TaxaMask 第四轮架构优化统一人工验收卡

日期：2026-07-11

候选分支：`codex/taxamask-architecture-refactor-round4`

目标：确认第四轮只改变代码责任归属和后台安全边界，没有改变你的标注、文献证据、训练真值、TIF 真值或导出结果。

## 1. 启动与项目

- [ ] 启动程序，Start Center 可正常操作，没有长时间白屏或报错。
- [ ] 打开一个代表性 2D SQLite 项目，图片、部位、已保存标注和 taxon 正确恢复。
- [ ] 关闭并重开同一项目，刚才的修改仍存在。
- [ ] 运行图片导入、训练、批量预测、VLM 或导出时尝试打开另一项目，程序应提示任务仍在运行并阻止切换。

## 2. 2D/STL 标注

- [ ] 连续切换多张图片和多个部位，没有明显卡点或错误跳图。
- [ ] 同一图片重新选择时视野和标注正常，不重复出现明显加载等待。
- [ ] 画一个 manual polygon 和 manual ROI box，保存后重开仍正确。
- [ ] 使用一次 SAM box/point；在 SAM 返回前切换图片，结果应写回发起提示的原图片，不污染新图片。
- [ ] 删除当前图片和末尾图片，选择分别落到合理的下一张/上一张。
- [ ] panel split、图片分组和训练 scope 仍按预期工作。
- [ ] 文献描述优先匹配当前图片来源数据库，来源信息可解释。

## 3. Blink 子部位

- [ ] 选择 parent 与 child，parent context、route 状态和 ROI box 正确。
- [ ] 打开 Child Expert Session，目标部位和 parent ROI 正确传入。
- [ ] 运行 child auto annotate 或 auto-shrink，结果仍是待复核草稿/轨迹，不覆盖人工真值。
- [ ] 打开当前 route expert settings，parent/child route 没有串到 parent 模型或 TIF backend。
- [ ] 子专家训练入口、进度和停止按钮行为正常。

## 4. 训练、预测、VLM 与导出

- [ ] 打开 2D/STL Model Settings，模型 profile、locator/segmenter、route 和 VLM 设置正确。
- [ ] 运行一个小型训练或至少完成 preflight，训练 scope 与 parent/child 角色正确。
- [ ] 运行当前图 prediction 或小批量 prediction，结果保持 AI draft，不覆盖 manual/confirmed label。
- [ ] 运行一个小规模 VLM current/batch，停止按钮能取消剩余队列；box-only draft 仍不能直接进入训练。
- [ ] 接受当前或批量 AI polygon draft 后，只有可复核 polygon 被确认。
- [ ] 导出一个小型 COCO/YOLO/multimodal 数据集，输出目录、样本数和 provenance 正常。

## 5. TIF/CT

- [ ] 打开代表性 TIF SQLite 项目，切换 specimen、part 和 reslice。
- [ ] 进入三维体预览，旋转、平移、缩放和切回切片模式无崩溃。
- [ ] 部位绑定的 label schema 重开后仍恢复为该部位保存的标签表。
- [ ] working edit、editable AI result、raw backup 和 manual truth 角色没有混淆。
- [ ] 检查一个真实 Local Axis reslice，方向和解剖结构符合预期。
- [ ] 大型已保存 reslice 选择时允许后台准备 preview，但界面不应出现此前的长时间无响应。

## 6. PDF、Agent 与界面

- [ ] 打开 PDF Evidence Tools，候选图片/描述仍作为证据或候选，不自动写成训练真值。
- [ ] 从 2D labeling 点击 Ask Agent，context 能看到当前 image/part、SQLite 项目、annotation/Blink/VLM 源码提示和安全说明。
- [ ] Ask Agent 新会话的第一个问题能返回正常正文；即使检查大型项目目录，也不会立即提示“聊天内容已压缩”或只显示“模型本轮没有返回可展示正文”。
- [ ] 从 TIF 点击 Ask Agent，context 能区分 selection loading、background preview、pending render 和旧数组释放。
- [ ] 打开 General、2D/STL Model、TIF Model 和 PDF API 设置。
- [ ] 切换中英文与深浅主题，菜单、按钮和主要状态文本正常。
- [ ] 正常关闭程序，待保存和后台任务提示可理解。

## 7. 验收结论

- [ ] 全部通过，第四轮候选可标记 `accepted`。
- [ ] 存在问题，需要记录具体项目、操作步骤、预期和实际结果。

验收备注：

```text
项目/数据：
失败步骤：
预期结果：
实际结果：
是否可稳定复现：
```
