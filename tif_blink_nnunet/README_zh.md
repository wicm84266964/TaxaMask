# TIF-Blink nnU-Net v2 适配探索包

这个目录是独立实验包，不覆盖现有 `tif_blink/` 2.5D U-Net 原型，也暂不接入 TaxaMask。

目标是把 TIF-Blink 的训练方法迁移到 nnU-Net v2 的 3D patch 训练中：

- 3D label patch 生成 boundary band。
- 3D image patch 生成 `normal / inside_band / outside_band` 三视图。
- `normal` 做完整分割监督。
- `inside_band` 重点监督边界带内分类。
- `outside_band` 使用低权重监督。
- 三视图之间在 boundary band 内做 consistency loss。

## 文件说明

- `boundary3d.py`：3D 材料边界和边界带生成。
- `views3d.py`：3D Blink 三视图生成。
- `losses3d.py`：3D grouped-view loss。
- `metrics3d.py`：3D boundary dice。
- `nnunet_trainer.py`：`nnUNetTrainerTifBlink` 原型。

## 使用边界

当前 trainer 是第一版原型：

- 保留 nnU-Net v2 的 planning、preprocessing、dataloader、validation、prediction。
- 只在 `train_step` 中将 batch 扩展成三视图并计算 TIF-Blink loss。
- 第一版只使用 full-resolution target；deep supervision 多尺度 boundary loss 后续再做。
- 推理时仍使用 nnU-Net v2 normal 图像推理，不需要 boundary band。

## 在 nnU-Net v2 环境中测试

模型测试机器需要能 import 到 `tif_blink_nnunet.nnunet_trainer.nnUNetTrainerTifBlink`。

建议先做最小 smoke：

1. 将 `tif_blink_nnunet/` 放到训练项目的 Python path。
2. 确认：

```bash
python -c "from tif_blink_nnunet.nnunet_trainer import nnUNetTrainerTifBlink; print(nnUNetTrainerTifBlink)"
```

3. 使用 nnU-Net v2 自定义 trainer 方式指定 `nnUNetTrainerTifBlink` 训练小数据集。

## 当前不做

- 不导出 TaxaMask 数据。
- 不导入 TaxaMask `model_draft`。
- 不替换现有 2.5D `tif_blink/`。
- 不声称优于标准 nnU-Net v2，需要先做同 fold 对比。

