# 物种与个体工作台：外部模型契约 v1

本契约专用于 `species_instances_2d` 项目。现有 2D/STL 的按部位字典契约保持原样，不能用于同种多个体。

## 配置入口

主界面 → 物种与个体标注 → 模型设置。训练/预测可选内置 Ultralytics 或外部脚本；SAM 辅助描边独立配置。

外部配置包括后端 ID、显示名、Python 解释器、准备/训练/预测命令、模型清单路径、支持任务、数据格式、超时以及有效训练参数 JSON。设置保存在当前实例项目 SQLite 的 settings 中，不改变其他工作台配置，也不写入导出的标注快照。不要把 API 密钥写进命令；外部程序自行通过运行环境读取必要凭据。

命令示例：

```text
"{python}" "path/to/adapter.py" --contract "{contract_json}"
```

占位符为 `{python}`、`{contract}`/`{contract_json}`、`{run_dir}`。沿用 `render_external_command`，不经过 shell，不支持 `&&`、管道或重定向。命令必须含契约路径；解释器、脚本及路径可以包含空格。

## 请求

`schema_version = taxamask-instance-backend-v1`，action 为 `prepare`、`train` 或 `predict`，task 为 `detect`、`segment` 或 `classify`。

- 公共身份：project_id、revision、categories、category_map_hash、run_dir。
- 训练：dataset_dir 指向完成导出目录，snapshot_json 是冻结输入，initial_weights 是经校验的初始文件副本；effective_config 为训练账本记录的有效参数，train_params 为项目配置。model_manifest 是指定结果位置。
- 准备：可选；衍生文件应写在 run_dir。禁止改写已校验的数据集或标签，准备后会再次验证导出输入。
- 预测：image_uid、image_hash、image_path、width、height、instance_id、model_manifest、prediction_json。分类请求的图片是所选实例裁剪，instance_id 非空；检测/分割请求是整图。

categories 使用稳定 category ID。category_map_hash 为排序后的 category ID 数组的规范 JSON 的 SHA-256；类别更名不会改变身份，新增/删除类别会改变该哈希。

## 预测响应

写入 prediction_json，最多 64 MiB。必须原样返回项目、修订、图像和类别身份：

```json
{
  "schema_version": "taxamask-instance-prediction-v1",
  "project_id": "instance_project_example",
  "revision": 12,
  "image_uid": "image_example",
  "image_hash": "sha256-value",
  "category_map_hash": "sha256-value",
  "task": "detect",
  "instances": [
    {"proposal_id": "p1", "category_id": "category_a", "bbox_xyxy": [10, 20, 40, 60], "score": 0.9},
    {"proposal_id": "p2", "category_id": "category_a", "bbox_xyxy": [60, 20, 90, 60], "score": 0.8}
  ]
}
```

同类多个对象用数组表达，proposal_id 在响应内唯一。坐标为方向校正后的像素 xyxy，越界、退化、非有限数、未知类别或错版本均拒绝；不默默截断或重分类。

分割每个对象另有 `mask_rle`，为 COCO RLE（size 为 `[height,width]`），掩膜必须非空、同尺寸；保留孔洞和断开区域。分类仅返回一个类别建议，无框；它绑定本次所选实例，不能作为整图物种确认。

界面展示候选，采用后仍为 draft。取消、过期结果、失败输出不覆盖人工标注。

## 模型清单

```json
{
  "schema_version": "taxamask-instance-external-model-v1",
  "task": "detect",
  "category_map_hash": "sha256-value",
  "weights": "model/weights.bin",
  "weights_hash": "sha256-value",
  "effective_config": {}
}
```

weights 为相对清单目录的文件路径，不能越界；weights_hash 为完整文件 SHA-256。训练响应必须回传与契约一致的 effective_config。后端若不能实现请求参数，应报错而不是忽略；算法特有参数在配置的 train_params 中显式记录。清单和权重经校验后登记为现有 TrainingRunRecorder 的输出产物。

运行产物位于 `<项目>/runs/<run_id>/`：契约、有效参数、logs、模型清单、权重与 ledger。超时/取消终止外部直接子进程；外部适配器不得脱离父进程自行启动后台服务。强制终止时账本可能记录 interrupted，界面同时保留用户取消状态，不虚报成功。

## 验证口径

自动测试使用小型外部适配脚本验证真实子进程、带空格路径、两只同类对象、COCO 训练输入、共享账本、身份拒绝及草稿边界。这证明调用契约可用，不表示任意第三方模型都已验证。接入新后端还需验证其真实训练、预测和参数执行情况。
