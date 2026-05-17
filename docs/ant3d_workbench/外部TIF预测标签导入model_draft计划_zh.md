# 外部 TIF 预测标签导入 model_draft 计划

## 1. 背景

当前 TIF 工作台已有三类入口：

- `导入 TIF stack`：导入原始三维图像体数据，创建 `working_image` 和空 `working_edit`，不创建 `manual_truth`。
- `导入 AMIRA 目录`：只读导入历史 AMIRA/Avizo 人工标注，生成 `manual_truth`、`working_edit` 和 `material_map.json`。
- `运行预测并导入草稿`：通过 TaxaMask TIF backend contract 运行后端，再把预测结果导入 `model_draft`。

缺口是：研究者已经在 TaxaMask 外部用 nnU-Net 或类似工具跑出一份 label `.tif/.tiff` 时，没有直接把这份粗标注导入 TIF 项目的入口。

## 2. 产品边界

新增入口应表达为“导入外部预测标签 TIF”，而不是“导入 TIF stack”。

导入结果必须进入：

- `labels/model_draft/<prediction_id>.ome.zarr/`

不得自动进入：

- `labels/manual_truth.ome.zarr/`

研究者需要先检查切片、必要时复制到 `working_edit` 修改，再手动确认提升为 `manual_truth`。

## 3. 安全规则

- 必须已有目标 specimen 和 `working_image`。
- 预测标签 TIF 必须是 3D，shape 必须与目标 specimen 的 `working_image.shape_zyx` 一致。
- dtype 作为 label ID 保存，建议使用整数类型；非整数类型默认拒绝。
- 导入后记录 `prediction_id`、`source_model`、源文件路径和导入报告。
- 不覆盖已有 `manual_truth`，不改变 train-ready 状态。

## 4. UI 入口

在 TIF 工作台模型训练区新增按钮：

`导入外部标签 TIF 到草稿`

操作流程：

1. 选择当前 specimen。
2. 选择外部 label `.tif/.tiff`。
3. 输入 prediction ID，默认取文件名加时间戳。
4. 可输入 source model，例如 `nnUNet`。
5. 导入后自动切到 `model_draft` 层查看。

## 5. 验证

- core 测试：合法 label TIF 能生成一个 `model_draft`。
- core 测试：shape 不一致会拒绝，且不新增 draft。
- UI smoke：按钮存在并有中文文案。
