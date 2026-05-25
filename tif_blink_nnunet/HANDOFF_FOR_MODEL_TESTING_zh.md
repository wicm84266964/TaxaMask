# TIF-Blink nnU-Net v2 模型测试交付说明

## 交付内容

本目录 `tif_blink_nnunet/` 是独立探索包，用于测试 TIF-Blink 方法与 nnU-Net v2 的适配。它不依赖 TaxaMask 项目结构，也不覆盖现有 `tif_blink/`。

核心文件：

- `boundary3d.py`：3D boundary band。
- `views3d.py`：3D normal / inside_band / outside_band 三视图。
- `losses3d.py`：3D TIF-Blink grouped loss。
- `metrics3d.py`：3D boundary dice。
- `nnunet_trainer.py`：稳定导入入口。
- `_nnunet_trainer_impl.py`：实际 `nnUNetTrainerTifBlink` 实现。

## 当前验证状态

本机 `antsleap` 环境有 PyTorch，但没有 nnU-Net v2。

已验证：

```bash
python -m unittest tests.test_tif_blink_nnunet_core -v
```

结果：

```text
Ran 5 tests
OK
```

已验证内容：

- 3D boundary band 能生成。
- 3D 三视图 shape 正确。
- inside/outside 弱化逻辑生效。
- 3D grouped loss 可反向传播。
- 3D boundary dice 可计算。
- `nnUNetTrainerTifBlink` 符号可导入。

未在本机验证：

- 真实 nnU-Net v2 trainer 实例化。
- `nnUNetv2_train` 命令调用。
- deep supervision 多尺度输出。

原因：本机 `antsleap` 环境没有安装 `nnunetv2`。

## 模型测试机器的准备

请确认训练环境中：

```bash
python -c "import torch; import nnunetv2; print(torch.__version__, nnunetv2.__file__)"
```

然后确认：

```bash
python -c "from tif_blink_nnunet.nnunet_trainer import nnUNetTrainerTifBlink; print(nnUNetTrainerTifBlink)"
```

## 训练使用建议

第一轮建议使用已预处理好的小数据集做 smoke test：

- patch 尺寸不要太大。
- batch size 先从 1 开始。
- 先使用 no-deep-supervision 或确认 nnU-Net 输出主尺度可取。
- 先只跑 1 fold、1-5 epoch。

目标不是立即追求分数，而是确认：

- trainer 能被 nnU-Net v2 找到。
- batch 中 `data` 为 `[B, C, D, H, W]`。
- target 可转成 `[B, D, H, W]`。
- 三视图前向不会爆 shape。
- loss 可反向传播。
- checkpoint 能保存。

## 当前 trainer 设计边界

`nnUNetTrainerTifBlink` 当前只改训练 step：

- 输入 normal patch。
- 根据 label patch 生成 3D boundary band。
- 生成 normal / inside_band / outside_band 三视图。
- 三视图合并前向。
- 计算 TIF-Blink grouped loss。

保留 nnU-Net v2 的：

- planning。
- preprocessing。
- dataloader。
- validation。
- prediction。

当前限制：

- 第一版只使用 full-resolution target。
- 若 nnU-Net 返回 deep supervision 多尺度输出，只取第一个输出。
- 暂未实现多尺度 boundary band 下采样。
- 暂未实现 boundary-aware nnU-Net sampler。

## 需要重点观察的失败类型

如果训练失败，请记录：

- `data` shape。
- `target` shape。
- network output 类型和 shape。
- 是否 deep supervision 输出 list/tuple。
- `label_manager.num_segmentation_heads` 是否可用。
- CUDA OOM 发生在哪一步。
- loss 是否出现 NaN。

## 后续根据测试结果决定

如果 smoke test 通过：

- 增加多 epoch 训练。
- 与标准 nnU-Net v2 `3d_fullres` 做同 fold 对比。
- 记录 mean Dice、boundary Dice、surface Dice、体积偏差。

如果 deep supervision 不兼容：

- 做 `nnUNetTrainerTifBlinkNoDeepSupervision` 分支。
- 或实现多尺度 target/boundary 下采样。

