# TIF-Blink 对接 nnU-Net v2 需求与改动文档

## 目标结论

TIF-Blink 应定位为一种脑区边界训练方法，而不是固定的 2.5D U-Net 模型。当前 `tif_blink` 小 U-Net 用来快速验证方法；真正追求 3D 脑区分割效果时，应将 TIF-Blink 的边界弱化一致性训练逻辑迁移到 nnU-Net v2 的 3D 训练流程中。

对接分两层：

1. **标准 nnU-Net v2 baseline 对接**：不改 nnU-Net 内部，只把 TaxaMask TIF 项目导出成 nnU-Net v2 数据集格式，训练标准 `3d_fullres`，预测后回写 `model_draft`。
2. **TIF-Blink nnU-Net Trainer**：实现自定义 `nnUNetTrainer`，在 nnU-Net v2 的 3D patch 训练里加入 TIF-Blink 的三视图、边界带监督和 consistency loss。

## 参考依据

- nnU-Net v2 官方数据集格式文档说明，数据由 raw images、segmentation maps 和 `dataset.json` 组成。
- nnU-Net v2 官方扩展文档说明，修改训练过程时应扩展自定义 trainer，而不是重写整个框架。
- 自定义 trainer 的模型在其他机器上继续训练或推理时，trainer 类必须可导入。

## 当前 TIF-Blink 与 nnU-Net v2 的差异

| 项目 | 当前 TIF-Blink | nnU-Net v2 |
|---|---|---|
| 模型维度 | 2.5D U-Net，输入相邻切片，输出当前切片 | 支持 2D、3D fullres、级联等配置 |
| 数据单位 | slice / grouped slice | 3D patch |
| 预处理 | percentile normalization | 自动 fingerprint、resampling、normalization、planning |
| 推理 | 逐切片体推理 | 3D sliding-window + fold ensemble + postprocessing |
| 训练方法 | 已有三视图边界弱化一致性训练原型 | 默认无 TIF-Blink 逻辑，需要 custom trainer |
| TaxaMask 安全边界 | 已遵守 `manual_truth -> model_draft` | 需要外层适配保持这个安全边界 |

## 总体原则

- 不从零重写 nnU-Net v2。
- 第一阶段先建立标准 nnU-Net v2 baseline。
- 第二阶段只扩展 trainer，不破坏 nnU-Net v2 的 planning、preprocessing、patch sampling、inference 主体优势。
- 训练输入只允许使用 TaxaMask `manual_truth`。
- 预测输出只允许回写到 TaxaMask `model_draft`。
- 材料 ID 映射必须保存，并能在预测后还原。
- 自定义 trainer 必须可复制、可导入、可复现。

## 阶段 A：TaxaMask -> nnU-Net v2 Baseline

### 目标

把现有 TaxaMask TIF 项目导出为 nnU-Net v2 数据集，跑标准 3D baseline，得到可比较的基础分数。

### 预估工期

2-4 个工作日。

### 涉及改动

新增模块建议：

- `tif_blink/nnunet_export.py`
- `tif_blink/nnunet_import.py`
- `tif_blink/nnunet_manifest.py`
- `tests/test_tif_blink_nnunet_export.py`

### 功能需求

- 从 `TifProjectManager` 读取 train-ready specimens。
- 加载：
  - `working_volume`
  - `labels.manual_truth`
  - `material_map.json`
- 导出 nnU-Net v2 数据集目录：
  - `imagesTr/`
  - `labelsTr/`
  - `imagesTs/` 或预测输入目录
  - `dataset.json`
- 保存 TaxaMask 材料 ID 映射：
  - TaxaMask material ID -> nnU-Net label ID
  - nnU-Net label ID -> TaxaMask material ID
- 支持生成 run manifest，记录：
  - TaxaMask project path
  - specimen IDs
  - material mapping
  - spacing/orientation 信息
  - nnU-Net dataset ID/name
  - 导出时间
- 调用或提示用户调用：
  - `nnUNetv2_plan_and_preprocess`
  - `nnUNetv2_train`
  - `nnUNetv2_predict`
- 将预测结果导回 TaxaMask：
  - 还原材料 ID。
  - shape 必须与 `working_volume` 一致。
  - 写入 `labels/model_draft/<prediction_id>.ome.zarr`。
  - 生成 prediction report。
  - 不修改 `manual_truth`、`working_edit`、`train_ready`。

### 阶段 A 验收标准

- 能从一个小型 TaxaMask TIF 测试项目导出 nnU-Net v2 数据集目录。
- `dataset.json` 包含正确 labels、channel_names、file_ending。
- material ID 映射可往返还原。
- 预测导入只生成 `model_draft`，不覆盖 `manual_truth`。
- 标准 nnU-Net v2 baseline 能在训练机器上启动。

## 阶段 B：TIF-Blink nnU-Net v2 Custom Trainer

### 目标

在 nnU-Net v2 的 3D patch 训练中加入 TIF-Blink 边界弱化一致性训练。

### 预估工期

- 最小可跑原型：1-2 周。
- 可与标准 nnU-Net baseline 严肃比较的研究版：3-5 周。
- 可迁移、可复现、文档完整版本：6-8 周。

### 涉及改动

新增建议：

- `tif_blink/nnunet_trainer/nnUNetTrainerTifBlink.py`
- `tif_blink/nnunet_trainer/boundary_views_3d.py`
- `tif_blink/nnunet_trainer/losses_3d.py`
- `tif_blink/nnunet_trainer/metrics_3d.py`
- `tif_blink/nnunet_trainer/README_zh.md`
- `tests/test_tif_blink_nnunet_trainer_logic.py`

也可根据 nnU-Net v2 运行方式，将 trainer 文件复制或安装到 nnU-Net 可发现的位置。关键要求是：训练与推理机器必须能 import 到 `nnUNetTrainerTifBlink`。

### Trainer 核心逻辑

输入仍使用 nnU-Net v2 正常 data loader 给出的 3D patch：

```text
image: [B, C, D, H, W]
label: [B, D, H, W]
```

Trainer 内部生成三视图：

```text
views: [B, 3, C, D, H, W]
```

三视图含义：

- `normal`：原始 3D patch。
- `inside_band`：3D boundary band 内保留，band 外弱化。
- `outside_band`：3D boundary band 内弱化，band 外保留。

训练 loss：

- `normal`：完整 CE + Dice 主监督。
- `inside_band`：主要在 3D boundary band 内监督。
- `outside_band`：低权重监督，防止边界弱化后预测外扩。
- `normal` 与弱化视图之间：boundary-band consistency loss。
- 指标：mean Dice + boundary Dice。

### 3D boundary band 要求

- 从 3D label patch 生成材料界面。
- 支持 `radius_xy` 与 `radius_z` 分开设置。
- 必须考虑 spacing：
  - z spacing 粗时，`radius_z` 应更小。
  - xy spacing 细时，`radius_xy` 可相对更大。
- 默认不把背景外轮廓作为边界收缩对象，除非明确配置。

### deep supervision 策略

第一版建议：

- 先实现 no-deep-supervision 或仅主输出版本，降低复杂度。

第二版再支持：

- 对 nnU-Net 多尺度输出分别下采样 label 与 boundary band。
- 每个尺度计算对应 TIF-Blink loss。
- 按 nnU-Net 原有 deep supervision 权重聚合。

### 采样策略

nnU-Net v2 已有成熟 patch sampling 与前景过采样。TIF-Blink 不应粗暴替换。

建议策略：

- 第一版不改采样，只改 trainer loss。
- 第二版增加 boundary-aware patch weighting 或 boundary-rich case sampling。
- 采样策略必须写入 manifest，方便复现实验。

### 推理策略

推理时不生成三视图，只使用 normal 图像。

保留 nnU-Net v2 原有：

- 3D sliding-window inference。
- fold ensemble。
- postprocessing。

推理结果再通过 TaxaMask 导入层写为 `model_draft`。

## 阶段 C：对比实验与验收

### 目标

证明 TIF-Blink nnU-Net Trainer 是否真的改善脑区边界，而不是只增加复杂度。

### 实验对照

至少比较：

1. 当前 TaxaMask 外部 nnU-Net v2 标准方案。
2. nnU-Net v2 standard `3d_fullres`。
3. `nnUNetTrainerTifBlink`。
4. 可选：当前 2.5D TIF-Blink 小 U-Net。

### 指标

- mean Dice。
- per-region Dice。
- boundary Dice。
- surface Dice 或 Hausdorff 95。
- 小脑区召回率。
- 预测体积偏差。
- 人工审核时外扩/边界变胖案例数。

### 验证拆分

必须按 specimen 分组拆分训练/验证。

禁止：

- 同一个脑体的不同切片同时出现在 train 和 val。
- 用 `model_draft` 当训练真值。

## 风险与注意事项

### 风险 1：自定义 trainer 破坏 nnU-Net 稳定性

处理：

- 第一版只改 loss 与 batch 视图生成。
- 不改 planning。
- 不改 preprocessing。
- 不改 inference。

### 风险 2：consistency loss 抹平真实细边界

处理：

- `consistency_weight` 默认小。
- 必须记录 boundary Dice。
- 必须保留标准 nnU-Net baseline 对照。

### 风险 3：3D boundary band 半径不合理

处理：

- `radius_z` 与 `radius_xy` 分开配置。
- 根据 spacing 自动建议默认值。
- manifest 中记录实际半径。

### 风险 4：材料 ID 映射出错

处理：

- 所有训练导出与预测导入都必须记录 mapping。
- 测试非连续 ID，例如 `0, 5, 12, 37`。
- 预测导入前验证 label ID 是否都在 mapping 中。

### 风险 5：trainer 分发后其他机器无法推理

处理：

- 打包 trainer 文件。
- 写清安装方式。
- 训练 manifest 记录 trainer class name 与代码版本。
- 另一台机器恢复训练/推理前先做 import 检查。

## 执行清单

### A. Baseline 对接

- [ ] 新增 nnU-Net dataset export 模块。
- [ ] 新增 material ID mapping manifest。
- [ ] 新增 dataset.json 生成。
- [ ] 新增预测导入 `model_draft` 模块。
- [ ] 新增小型 TaxaMask 项目导出测试。
- [ ] 在训练机跑标准 nnU-Net v2 baseline。

### B. Custom Trainer 原型

- [ ] 新建 `nnUNetTrainerTifBlink`。
- [ ] 实现 3D boundary band 生成。
- [ ] 实现 3D inside/outside weak view。
- [ ] 实现 grouped 3D loss。
- [ ] 支持 no-deep-supervision 第一版。
- [ ] 训练 history 记录 loss 分量与 boundary Dice。
- [ ] 在小数据上跑通 1 fold smoke test。

### C. 研究版对比

- [ ] 支持 deep supervision。
- [ ] 增加 boundary-aware sampling 实验开关。
- [ ] 与标准 `3d_fullres` 同 fold 对比。
- [ ] 输出评估报告。
- [ ] 汇总失败案例给人工审核。

### D. 迁移与复现

- [ ] 打包 custom trainer。
- [ ] 写安装说明。
- [ ] 写训练命令模板。
- [ ] 写预测导入 TaxaMask 命令模板。
- [ ] 在另一台机器做恢复训练或推理测试。

## 当前不做

- 不直接替换当前 2.5D TIF-Blink。它继续作为方法原型和快速 smoke test。
- 不从零重写 nnU-Net v2。
- 不把 TIF-Blink 边界带作为推理输入。
- 不让模型输出覆盖 `manual_truth`。
- 不在没有 baseline 的情况下声称 TIF-Blink 优于 nnU-Net v2。

