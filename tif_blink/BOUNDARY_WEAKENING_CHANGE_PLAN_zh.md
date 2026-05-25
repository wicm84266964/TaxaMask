# TIF-Blink 边界弱化一致性训练改造方案

## 背景判断

当前 TIF-Blink 已经具备基础训练框架：

- 2.5D U-Net 多类别脑区分割。
- `normal / inside_band / outside_band` 三类训练视图。
- 边界带生成与 boundary-weighted CE。
- checkpoint、history、model manifest、TaxaMask `manual_truth -> model_draft` 安全边界。

但当前实现仍更接近“多视图数据增强 U-Net”，还不是完整的 TIF-Blink 训练方法。核心原因是：虽然图像层面已经做了边界弱化，但训练 loss 仍把所有视图当成普通完整监督样本处理。

这会带来一个逻辑风险：

- 遮挡或弱化后的图像信息不足。
- 如果仍要求模型在所有视图上都精确预测完整标签，模型可能学会猜测，而不是学会边界收敛。

因此下一步改造重点不是继续增加工程外壳，而是把训练目标改成真正适配脑区标注的边界弱化一致性训练。

## 目标定义

TIF-Blink 的脑区训练目标应定义为：

> 在正常图像上学习完整脑区分割；在边界被弱化或扰动时，学习保持脑区边界稳定、不过度外扩、不变松变粗。

它对应 STL/2D Blink 的迁移关系是：

- STL/2D Blink：从松框收缩到小部位极限提示框。
- TIF-Blink：从模糊/弱化边界收敛到稳定、薄、不过度扩张的脑区边界。

## 外部智能体建议的吸收原则

有价值，优先吸收：

- 三视图成组训练。
- `consistency_loss`。
- `boundary_dice`。
- `BalancedSliceSampler`。
- 训练 history 中记录 loss 分量与边界指标。

有价值，但排在后面：

- TensorBoard。
- EarlyStopping。
- LR Scheduler。
- sliding-window inference。

暂不吸收或不作为默认：

- BCE 作为主 loss。脑区分区是多类别互斥，默认仍使用 CrossEntropy + Dice。
- 将边界带作为模型输入通道。边界带来自人工标签，推理时没有，不能让模型偷看答案。
- 大规模重写 `__init__.py` 暴露所有模块。
- 未见源码的 `run.py / callbacks.py / pyproject` 结构调整。

## 目标训练结构

同一个 Z 切片应返回一组三视图：

- `normal`：原始 2.5D 切片堆叠。
- `inside_band`：边界带保留，边界带外弱化。
- `outside_band`：边界带弱化，边界带外保留。

训练时对三视图采用不同目标：

- `normal`：完整监督，计算全图 CE + Dice。
- `inside_band`：主要在 boundary band 内监督，训练边界附近分类。
- `outside_band`：低权重监督，避免模型因边界信息弱化而外扩。
- 三视图之间：计算一致性约束，防止预测在边界扰动下大幅摇摆。

## 需要新增或修改的模块

### 1. `dataset.py`

当前状态：

- 每个 dataset item 是单个 view。
- 三种 view 被展开成三条训练样本。

目标状态：

- 增加 grouped-view dataset 模式。
- 每个 item 返回：
  - `images`: shape `[3, C, H, W]`
  - `label`: shape `[H, W]`
  - `boundary`: shape `[H, W]`
  - `view_modes`: `["normal", "inside_band", "outside_band"]`
  - `specimen_id`

保留当前单视图 dataset，以免破坏已有 smoke test 和简单训练路径。

### 2. `losses.py`

新增：

- `masked_cross_entropy`
- `masked_dice_loss`
- `consistency_loss`
- `boundary_weighted_dice_loss`

保留：

- `boundary_weighted_cross_entropy`
- `soft_dice_loss`

默认训练仍使用多类别 CE + Dice，不将 BCE 作为主路径。

### 3. `metrics.py`

新增：

- `boundary_dice`

用途：

- 单独评价边界带内的 Dice。
- 判断模型是否在脑区边界附近变胖、变松、外扩。

### 4. `train.py`

新增 grouped-view 训练路径：

- `TifBlinkTrainConfig` 增加 loss 权重：
  - `normal_loss_weight`
  - `inside_boundary_loss_weight`
  - `outside_loss_weight`
  - `consistency_weight`
  - `boundary_dice_weight` 或 boundary dice 指标记录
- 增加 `_grouped_view_loss`。
- history 中记录：
  - `normal_loss`
  - `inside_boundary_loss`
  - `outside_loss`
  - `consistency_loss`
  - `total_loss`
  - `mean_dice`
  - `boundary_dice`

保留当前 `train_model` 简单路径，新增 grouped 训练接口或通过 config 显式开启。

### 5. `sampler.py`

新增：

- `BalancedSliceSampler`

逻辑：

- 根据 boundary density 提高有边界信息切片的采样概率。
- 增加异常保护：如果 boundary density 超过阈值，则退化为均匀采样或截断权重。

默认先不强制启用，只作为训练配置选项。

### 6. `tests/test_tif_blink_core.py`

新增测试：

- grouped dataset 返回三视图。
- 三视图 shape 正确。
- `inside_band / outside_band` 与 boundary band 对齐。
- `consistency_loss` 可反向传播。
- `boundary_dice` 能区分边界错误。
- grouped training smoke test 可在 torch 环境跑通。

## 执行清单

### 第一阶段：训练目标改造

- [x] 新增 grouped-view dataset，不移除现有单视图 dataset。
- [x] 新增 grouped collate 或保证默认 DataLoader 能正确堆叠 `[3,C,H,W]`。
- [x] 新增 masked CE / masked Dice。
- [x] 新增 consistency loss。
- [x] 新增 boundary dice 指标。
- [x] 新增 grouped-view loss 计算。
- [x] 在 history 中记录各 loss 分量。
- [x] 补充不依赖 GPU 的单元测试。
- [x] 使用 `antsleap` conda 环境跑 torch 测试。

### 第二阶段：采样优化

- [x] 新增 `sampler.py`。
- [x] 实现 boundary density 计算。
- [x] 实现 `BalancedSliceSampler`。
- [x] 增加 density 过高保护。
- [x] 增加采样器测试。
- [x] 在训练配置中增加可选启用开关。

### 第三阶段：训练可观察性

- [ ] 增加 EarlyStopping 配置。
- [ ] 增加 ReduceLROnPlateau 配置。
- [ ] 增加 TensorBoard 可选记录。
- [ ] 将这些工程增强保持为可选，不影响最小训练路径。

### 第四阶段：大体数据推理

- [ ] 新增 sliding-window inference 设计。
- [ ] 支持 patch size、overlap、blend mode。
- [ ] 支持大体数据逐块预测。
- [ ] 保证输出仍只写入 `model_draft`。

## 验收标准

第一阶段完成后至少满足：

- `python -m pytest tests/test_tif_blink_core.py -q` 在普通环境通过非 torch 测试。
- `antsleap` conda 环境下 `python -m unittest tests.test_tif_blink_core -v` 全部通过。
- GPU smoke test 能完成：
  - grouped 三视图训练。
  - checkpoint 保存。
  - checkpoint 加载。
  - 完整体数据推理。
- `manual_truth` 不被任何训练或推理流程修改。
- 预测结果仍写入 `model_draft`。

## 风险与处理

### 风险 1：一致性 loss 过强导致模型过度平滑

处理：

- `consistency_weight` 默认设小。
- history 中单独记录 consistency loss。
- 用 boundary dice 判断边界是否被抹平。

### 风险 2：inside/outside 视图监督过强导致模型学猜测

处理：

- `normal` 保持主监督。
- `inside_band` 只重点监督边界带。
- `outside_band` 使用低权重监督。
- 不在弱化视图上简单套完整强监督。

### 风险 3：采样器过度偏向边界切片

处理：

- boundary density 设置上限。
- 密度异常时退化为均匀采样。
- 在 manifest 中记录采样策略。

### 风险 4：训练接口变复杂

处理：

- 保留当前简单训练路径。
- grouped-view 训练通过显式配置开启。
- README 中区分“最小可跑路径”和“Blink 边界弱化路径”。

## 当前不做的事

- 不把 TIF-Blink 改成完整 nnU-Net。
- 不做 GUI 一键训练。
- 不默认启用边界输入通道。
- 不让 `model_draft` 参与训练。
- 不让推理结果自动覆盖 `manual_truth`。

## 当前实现记录

已完成第一阶段和第二阶段。当前 grouped-view 路径通过 `TifBlinkGroupedSliceDataset` 与 `TifBlinkTrainConfig(use_grouped_views=True)` 启用：

- `normal` 使用完整 CE + Dice 主监督。
- `inside_band` 只在 boundary band 内进行较强监督。
- `outside_band` 使用低权重监督。
- `normal` 与两个弱化视图之间计算 boundary-band consistency loss。
- history 记录 `normal_loss`、`inside_boundary_loss`、`outside_loss`、`consistency_loss`、`total_loss`、`mean_dice`、`boundary_dice`。
- balanced sampler 通过 `use_balanced_sampler=True` 可选启用，默认关闭。

验证记录：

- base 环境：`python -m pytest tests/test_tif_blink_core.py -q`，结果 `11 passed, 7 skipped`。跳过项为 PyTorch 相关测试。
- `antsleap` 环境：`python -m unittest tests.test_tif_blink_core -v`，结果 `18 tests OK`。
