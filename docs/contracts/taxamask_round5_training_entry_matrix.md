# TaxaMask 第五轮训练入口矩阵

状态：M1 实现后当前状态，更新于 2026-07-20。

本文件回答三个问题：有哪些真实训练入口、哪些数据可以训练、每次训练事实写到哪里。字段契约见 `taxamask_round5_artifact_contract_v1.md`。

## 1. 统一规则

- 项目 SQLite 是训练 run、实际配置、拆分、产物索引、终态、恢复状态和备注绑定的唯一权威。
- JSON 报告、模型 manifest 和历史文件只是可读投影或受索引产物，不是平级后端。
- 项目内入口只接受 Registry 复验通过的人工确认标签；未确认样本没有绕过开关。
- 每次训练先建 `pending`，预检通过后转 `running`，最后写 `succeeded`、`failed`、`cancelled` 或 `interrupted`。
- 重试创建新 run，并用 `retry_of` 引用原失败 run；历史不覆盖。
- 不区分“正式/临时训练”，用户通过 run 备注记录目的、重要性、结论和后续用途。

## 2. 入口与记录边界

| `entrypoint` | 用户入口 | SQLite 记录边界 | 当前状态 |
|---|---|---|---|
| `builtin_locator_sam` | 主窗口 Locator/SAM 训练 | `prepare_2d_training_run()` + `TrainingThread` | 已接入 |
| `headless_builtin_locator_sam` | `tools/agentic/train_project.py` | CLI 解析后即建 run，项目打开/预检/训练/权重发布均收敛终态 | 已接入 |
| `external_parent_script` | 二维外部父模型 | `ExternalBackendRunner.run_prepare_and_train()` | 已接入 |
| `blink_vit_b` | 主窗口或 Blink Lab | `prepare_blink_training_run()` + `BlinkTrainingThread` | 已接入 |
| `blink_heatmap` | 主窗口或 Blink Lab | 与 ViT-B 共用生命周期，后端事实分开记录 | 已接入 |
| `tif_external` | TIF 工作台自定义后端 | `TifBackendRunner.run_action("train")` | 已接入 |
| `tif_external_nnunet` | TIF 工作台 nnU-Net v2 预设 | TIF 通用生命周期 + nnU-Net 实际参数回执 | 已接入 |
| `local_axis_external` | Local Axis 模型面板 | `TifLocalAxisBackendRunner.run_action("train")` | 已接入 |
| `tif_blink_project` | `tif_blink train-project` | 项目打开前建 run，项目 SQLite 为权威 | 已接入 |
| `tif_blink_nnunet_preprocessed` | `tif_blink train-nnunet-preprocessed` | 输出目录 SQLite 为权威，强制可信来源说明 | 已接入 |

`tif_smoke_adapter` 只验证契约接线，固定 `usable_for_research_prediction=false`，不登记为研究可用模型。`external_blink` 仍只有预测能力，不得伪装成外部训练成功。

## 3. 真值与拆分门禁

| 入口组 | 可训练数据 | 拆分与额外门禁 |
|---|---|---|
| 二维 Locator/SAM | 人工确认 polygon；排除未复核 Auto-Annotated 草稿 | 稳定 train/validation 拆分；训练前复验图像、标签快照和起始权重 |
| Blink | 人工确认 shrink trajectory | 按 image UID 固定拆分；ViT-B 与 Heatmap 均记录实际后端参数 |
| TIF / nnU-Net | `manual_truth` 且 train-ready | 至少两个独立 specimen；nnU-Net 必须回传实际采用拆分，否则失败 |
| Local Axis | `human_confirmed=true` 且 `usable_for_training=true` | 至少两个独立 specimen group；当前 specimen/part 训练不混入其他部位 |
| TIF-Blink 项目入口 | train-ready specimen 的 `manual_truth` | 按 specimen 固定拆分，防止切片泄漏 |
| TIF-Blink 外部入口 | 显式声明可信来源的 nnU-Net 预处理数据 | 强制哈希 dataset/plans/fingerprint/split 与实际 b2nd 文件；禁止 case 跨集合 |

## 4. 实际配置与产物

所有入口统一记录：

- epochs、batch size、学习率、weight decay、随机种子和输入分辨率；
- 实际预处理、训练/验证拆分、模型与后端版本、设备和关键运行环境；
- 数据版本、实际输入清单、起始权重及完整性结果；
- 开始/结束时间、错误摘要、结果目录、报告、manifest 和权重哈希。

nnU-Net 的 epochs、batch、patch size、学习率和 weight decay 从实际 checkpoint/plans 解析，不填猜测值。dry-run 明确记录 `backend_dry_run` 和 `persist_weights=false`，不登记假权重。

模型清单和后端结果使用相对引用；旧绝对路径模型仍兼容读取。运行时 contract 可携带执行必需的绝对路径，但不得复制到 SQLite 事实记录、脱敏诊断或模型清单。

## 5. 备注与恢复

- run 备注保存在 SQLite，可编辑内容，但不能修改配置、哈希、拆分、产物和终态。
- 启动时把遗留 `pending/running` run 标记为 `interrupted`，不会列为成功模型。
- 文件不一致时训练保持停止，并进入统一善后：重新复验、同哈希重新定位/恢复副本、带说明登记新版本、导出脱敏诊断。
- 同哈希搬家只更新位置并留下迁移记录，不推进数据版本；内容变化必须生成新数据版本。

## 6. 代码与测试证据

- 完整性与 Registry：`file_integrity.py`、`project_integrity_registry.py`、`tif_integrity_bridge.py`。
- 生命周期与备注：`training_run_recorder.py`、`training_run_2d.py`、`training_run_tif.py`、`training_run_notes.py`。
- TIF / Local Axis：`tif_backend.py`、`tif_local_axis_ai.py`、`tif_nnunet_v2_backend.py`。
- TIF-Blink：`tif_blink/training_run.py`、`tif_blink/cli.py`、`tif_blink/train.py`。
- 回归测试：`test_file_integrity.py`、`test_training_run_recorder.py`、`test_training_run_2d.py`、`test_blink_training_run_lifecycle.py`、`test_tif_backend.py`、`test_tif_local_axis_ai.py`、`test_tif_blink_training_lifecycle.py`。
