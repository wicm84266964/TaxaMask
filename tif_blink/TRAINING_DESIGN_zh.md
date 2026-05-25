# TIF-Blink 完整训练框架设计规划

## 当前定位

TIF-Blink 是一个面向 TaxaMask TIF 体数据脑区标注的实验训练框架。它不是 STL/2D Blink 的直接搬运，也不是 SAM 提示框算法。迁移过来的核心思想是：

- 用不同遮挡视图训练模型，而不是只看原图。
- 把原 Blink 的“最小提示框收缩”改造为脑区边界不确定带的收缩学习。
- 使用 U-Net/nnU-Net 风格的多类别分割，而不是一个脑区一个模型。
- 模型输出永远先进入 `model_draft`，不能自动覆盖 `manual_truth`。

当前实现目标是先搭成可审计、可测试、可继续接入 TaxaMask 的 2.5D U-Net 训练框架。它不是最终生产级 nnU-Net 替代品。

## 训练数据边界

训练输入来自 TaxaMask TIF 项目中已经标记为 `train_ready` 的样本：

- `working_volume`：模型看到的 TIF 体图像。
- `labels.manual_truth`：人工审核后的训练真值。
- `material_map.json`：脑区材料 ID 和名称。

训练框架必须遵守：

- 只允许 `manual_truth` 作为训练标签。
- 不允许使用 `model_draft` 当训练真值。
- 预测结果只能写入 `labels/model_draft/`。
- 不能改变 `manual_truth`、`working_edit` 或 `train_ready` 状态。

## 材料 ID 映射

TaxaMask 的材料 ID 可能是 `0, 5, 12, 37` 这种不连续编号，而 PyTorch 多分类分割要求类别编号连续。因此训练时必须建立映射：

- TaxaMask 材料 ID -> 模型类别 ID：例如 `0 -> 0, 5 -> 1, 12 -> 2`
- 模型类别 ID -> TaxaMask 材料 ID：推理输出时还原

这个映射必须写入 checkpoint 和 model manifest，否则推理结果无法可靠回写到 TaxaMask。

## Blink 迁移逻辑

原 Blink 的关键不是固定模型，而是训练视图策略。TIF-Blink 中保留以下训练逻辑：

1. 从人工标签生成脑区之间的边界核心。
2. 将边界核心膨胀为边界不确定带。
3. 训练时交替喂入三类视图：
   - `normal`：原始 2.5D 切片堆叠。
   - `inside_band`：只强化/保留边界带附近信息，弱化边界外信息。
   - `outside_band`：弱化边界带附近信息，让模型不能只依赖模糊边界。
4. grouped-view 训练路径中，对三类视图使用不同训练目标：
   - `normal` 使用完整监督。
   - `inside_band` 重点监督边界带内分类。
   - `outside_band` 使用低权重监督。
   - 三视图之间使用 consistency loss，重点防止边界弱化后预测摇摆。

重要安全点：

- 边界带来自人工标签，推理时不可用。
- 因此边界带默认不能作为模型输入通道。
- 边界带只能默认用于训练视图生成和 loss 加权。
- 若实验性打开边界输入通道，必须视为调试/消融实验，不作为真实训练默认值。

## 模型架构

第一阶段使用 2.5D U-Net：

- 输入：当前 z 切片加上下文相邻切片，例如 `z-1, z, z+1`。
- 输出：当前 z 切片的多类别脑区标签。
- 所有脑区一起预测，类别之间互斥。

选择 2.5D 的原因：

- 比完整 3D U-Net 更容易在普通机器上跑通。
- 仍然能利用上下文切片，适合 TIF 堆栈早期实验。
- 便于后续迁移到 3D U-Net 或 nnU-Net 风格 patch trainer。

## 完整训练器应包含

训练器需要落成以下能力：

- 训练循环：多 epoch、AdamW 优化器、CE + Dice + boundary weighted loss。
- 验证循环：记录 validation loss、整体 Dice、各类别 Dice。
- checkpoint：保存 `best.pt` 和 `last.pt`。
- history：保存每个 epoch 的训练/验证指标。
- model manifest：记录模型结构、材料 ID 映射、训练配置、输入通道、训练样本。
- 设备选择：支持 `cpu`、`cuda`、`auto`。
- 可重复性：保存 seed，并设置 NumPy/PyTorch 随机种子。

## 推理器应包含

推理器需要：

- 从 checkpoint 恢复模型和材料 ID 映射。
- 对完整 ZYX 体数据逐切片或批量切片推理。
- 推理时使用 `normal` 视图，不使用人工边界带。
- 输出还原后的 TaxaMask 材料 ID 标签体。
- 保持输出 shape 与输入 `working_volume` 完全一致。

## TaxaMask 对接

对接层分两步：

1. 读取训练样本：
   - 从 `TifProjectManager` 中选取 train-ready specimen。
   - 加载 `working_volume` 和 `manual_truth` sidecar。
   - 生成 `TifBlinkSample`。

2. 写入预测草稿：
   - 将预测标签体写成 `ant3d_volume_sidecar`。
   - 路径位于 `specimens/<id>/labels/model_draft/<prediction_id>.ome.zarr`。
   - 调用 `add_model_draft` 注册到项目。
   - 生成预测报告，明确 `manual_truth_overwritten: false`。

## 当前实现阶段

本阶段应补齐：

- 训练器骨架。
- 验证指标。
- checkpoint 和 manifest 写入。
- 推理器骨架。
- TaxaMask 样本读取与 model_draft 写入桥接。
- 不依赖 PyTorch 的核心安全测试。

当前已补充：

- grouped-view dataset。
- masked CE / masked Dice。
- boundary-band consistency loss。
- boundary dice 指标。
- boundary-density balanced sampler。

暂不承诺：

- GUI 一键训练。
- 大体数据 patch sampler。
- 多 GPU。
- 真正 nnU-Net 自动规划。
- 3D U-Net。

这些内容在训练框架可跑通后再进入下一阶段。
