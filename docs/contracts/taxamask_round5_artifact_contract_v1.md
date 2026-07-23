# TaxaMask 第五轮运行产物契约 v1

状态：用户已整体确认，第一阶段冻结稿。后续只能向后兼容地补充可选字段，改变必需字段或既有字段含义必须先更新设计稿并重新评审。

对应需求：R-000、R-001、R-002、R-007、R-008、R-009、R-016。

## 1. 目的与边界

本契约统一四类可审计记录：

1. 文件完整性清单；
2. 训练运行记录及其实际拆分清单；
3. 推理运行及其分阶段事件；
4. 网格导出的 SQLite 权威记录与 STL 文件发布。

它不替代现有 TIF、Local Axis 或外部模型后端契约，也不改变人工真值规则。`working_edit`、`editable_ai_result`、`model_draft`、未接受 proposal 和未复核 `Auto-Annotated` polygon 均不得作为训练真值。

## 2. 通用规则

### 2.1 ID 与排他创建

- 每份记录必须包含字符串 `schema_version`、`status` 和该记录类型的稳定 ID。
- `run_id`、`manifest_id`、`split_id`、`event_id` 和 `export_id` 必须由 UTC 微秒时间、随机或 UUID 成分共同生成，例如 `train_20260718T073000123456Z_7f3a2c1d`。只有秒级时间戳不满足稳定 ID 要求。
- 创建 run/export 目录必须使用排他语义；目录已存在时不得使用 `exist_ok=True` 复用，必须重新生成 ID。SQLite 主键插入冲突时同样重新生成，不能覆盖旧记录。
- ID 只能包含 ASCII 字母、数字、点、下划线和连字符；不得包含路径分隔符。旧文件名时间戳只能作为产物名，不能承担事实主键。

### 2.2 时间、写入和敏感信息

- 时间使用带时区的 ISO 8601 字符串，例如 `2026-07-18T15:30:00+08:00`。
- 项目内的完整性版本、训练运行、训练拆分、产物索引、备注关联、网格导出状态及恢复处理只以项目 SQLite 为权威。项目尚未成功打开时产生的训练失败记录写入全局训练台账 SQLite，项目可用后再通过稳定 `run_id` 建立关联。
- 不建设 JSON/SQLite 平级后端。下文训练与完整性相关的 JSON 形状只用于说明逻辑字段，也可作为由 SQLite 原子导出的只读投影；JSON 缺失或损坏时只能从 SQLite 重建，不能据此恢复、覆盖或改变项目状态。
- 获准存在的 JSON manifest、report 或 JSONL 使用 `AntSleap.core.safe_io.atomic_write_json` 或同等原子流程；本规则不授权生成网格 JSON sidecar。
- 写入中断时不得留下可被识别为成功的正式记录；可恢复状态使用 `incomplete` 或 `interrupted`。
- 输出采用字段白名单，不保存 API 密钥、访问令牌、完整命令行、本机用户名或无必要绝对路径。外部命令只保存脱敏后的 backend/adapter 标识和实际生效参数。
- 事实字段一经进入完成终态不得被备注编辑覆盖。备注通过 `note_ref` 或独立备注记录关联。

### 2.3 路径规则

所有归档路径对象都必须同时保存 `path_base` 和 `relative_path`：

| `path_base` | 运行时含义 |
|---|---|
| `project_root` | 当前 TaxaMask 项目根 |
| `run_root` | 当前训练或处理 run 根 |
| `export_root` | 当前网格导出目录根 |
| `managed_model_root` | TaxaMask 管理的模型根 |
| `runtime_log_root` | 现有 `TaxaMask_outputs/runtime_logs/` 根 |

读取器和写入器必须遵守以下规则：

1. `relative_path` 使用 POSIX `/`，不得为空，不得以 `/` 或 `\\` 开头，不得包含反斜杠、Windows 盘符、UNC、NUL、空段、`.` 或 `..` 段。
2. `path_base` 必须是上表白名单值；未知基准不得猜测。
3. 解析后必须用规范化绝对路径做 containment 检查，确认目标仍在基准目录内。
4. 对已有文件使用解析符号链接后的真实路径复核；对待创建文件检查最近的已有父目录，并拒绝任何会借助 junction/symlink 逃出基准目录的路径。
5. 归档记录不得保存绝对路径。运行时确需绝对路径的外部 contract 不直接复制进统一记录；外部产物优先复制/快照到受管根。无法复制的外部产物只能使用 2.4 节定义的 `external_reference`，这是不使用 `path_base/relative_path` 的唯一例外。
6. 跨目录记录通过稳定 ID 关联，不使用 `../`。引用文件本身仍按其所属基准保存相对路径和哈希。

### 2.4 文件、artifact 与哈希

每个受管文件或 artifact 至少保存：

```text
artifact_id 或 file_id
role
path_base
relative_path
entry_kind = file | directory
size_bytes
hash_algorithm
digest
```

无法复制到受管根的外部产物使用以下唯一例外结构，不得混用受管路径字段：

```json
{
  "artifact_id": "external_checkpoint",
  "role": "output_weights",
  "entry_kind": "external_reference",
  "external_location_ref": "location_ref_7f3a2c1d",
  "size_bytes": 1048576,
  "hash_algorithm": "sha256",
  "digest": "8888888888888888888888888888888888888888888888888888888888888888"
}
```

- `external_location_ref` 是本机位置注册表中的不透明 ID，不得包含路径分隔符、盘符、UNC、用户名或可反推私人绝对路径的文本。
- `external_reference` 必须保存 `artifact_id`、`role`、固定的 `entry_kind: "external_reference"`、`external_location_ref`、`size_bytes`、`hash_algorithm` 和 `digest`，且不得保存 `path_base` 或 `relative_path`。
- 写入 `succeeded`、`verified` 或 `complete` 前，外部位置必须仍可访问并重新计算 size/digest；无法访问或不匹配时只能进入失败或不完整状态。

- 普通文件完整哈希使用 `hash_algorithm: "sha256"`；目录使用下述冻结的 `sha256-tree-v1`，不得由各入口自行定义遍历或拼接方式。
- 快速指纹必须使用独立、版本化的算法名，例如 `taxamask-sampled-sha256-v1`，不得标成 `sha256`。
- `size_bytes` 对目录表示所有普通成员文件的合计大小。mtime 只能帮助发现变化，不能替代 digest。
- `succeeded`、`verified` 或 `complete` 记录中的所有必需 artifact 必须具有非负 `size_bytes`、算法名和 digest。`missing` 状态允许三者为 `null`。
- 模型、报告、manifest、split、日志和 STL 使用同一字段结构，不再使用 `sha256`、`manifest_sha256` 等含义不同的单字段简写。

#### 2.4.1 `sha256-tree-v1`

`sha256-tree-v1` 必须按以下字节级规则实现，保证 OME-Zarr 等目录在三平台产生相同 digest：

1. 根目录及后代不得是 symlink、junction/reparse point、设备、socket 或其他特殊文件；不得跟随链接。发现任一此类条目时终止并记录 `incomplete`，不能跳过后继续标记已验证。
2. 递归枚举根目录下的所有普通文件和子目录；子目录条目本身必须进入摘要，因此空目录不会被忽略。根目录自身不作为条目，空根目录只计算固定头。
3. 相对路径使用 POSIX `/`，Unicode 规范化为 NFC 后编码为 UTF-8；若规范化后出现重名、空段、`.` 或 `..` 段则失败。
4. 所有条目按规范化相对路径 UTF-8 字节升序排列。摘要先写入 ASCII 固定头 `taxamask-sha256-tree-v1` 和一个 NUL 字节。
5. 每个条目依次写入：一个类型字节（目录为 ASCII `D`，文件为 ASCII `F`）、8 字节无符号大端路径长度、路径 UTF-8 字节、8 字节无符号大端内容长度。目录内容长度固定为 0；文件内容长度为实际字节数，随后分块写入原始文件字节。
6. mtime、权限、所有者和平台文件属性不进入摘要，但必须用于检测计算期间的并发修改。读取每个文件前后都要比较 size、`mtime_ns` 和平台可用的稳定文件标识（如 device/inode 或 Windows file ID），整个目录遍历前后也要比较成员集合与类型；任一变化都使本次结果为 `incomplete`，不得发布 digest。
7. 若文件系统不能提供可靠的高精度 mtime 或稳定文件标识，则必须从全新枚举开始完整计算第二遍，并要求两遍的成员元数据和 tree digest 完全一致；否则结果为 `incomplete`。这项稳定性检查只决定本次 digest 能否发布，不把平台元数据写入 digest。

### 2.5 错误字段

每类记录都必须包含 `error`。`pending`、`running`、`started`、`skipped` 以及成功终态的 `error` 必须为 `null`；跳过原因写入 `decision.reason_code`，不能伪装成错误。失败、缺失、中断或不完整状态使用以下对象：

```json
{
  "code": "source_digest_mismatch",
  "summary": "The source label no longer matches the recorded digest.",
  "stage": "integrity_verify",
  "recoverable": true,
  "diagnostic_artifact_id": "diagnostic_01"
}
```

`summary` 必须脱敏且适合直接提示用户；原始 traceback、命令行和环境转储只能作为经过白名单清理的诊断 artifact 保存。

## 3. 状态机与不变量

### 3.1 允许状态与转换

| 记录 | 允许状态 | 允许转换 |
|---|---|---|
| 完整性清单 | `pending`、`verified`、`mismatch`、`missing`、`incomplete` | `pending -> verified/mismatch/missing/incomplete`；`incomplete -> pending` 仅用于同一未完成校验的继续执行 |
| 训练拆分清单 | `pending`、`verified`、`failed`、`incomplete` | `pending -> verified/failed/incomplete`；`incomplete -> pending` 仅用于继续构建 |
| 训练运行 | `pending`、`running`、`succeeded`、`failed`、`cancelled`、`interrupted` | `pending -> running/failed/cancelled/interrupted`；`running -> succeeded/failed/cancelled/interrupted` |
| 推理运行 | `pending`、`running`、`succeeded`、`failed`、`cancelled`、`interrupted` | `pending -> running/failed/cancelled/interrupted`；`running -> succeeded/failed/cancelled/interrupted` |
| 推理阶段 | `started`、`succeeded`、`skipped`、`failed` | 同一 `stage_span_id` 先写一个 `started` 事件，再写至多一个终态事件；每个事件均不可变 |
| 网格导出 | `pending`、`running`、`complete`、`incomplete`、`failed` | `pending -> running/incomplete/failed`；`running -> complete/incomplete/failed`；`incomplete -> running` 仅用于原导出的继续校验或续写 |

程序启动恢复时，遗留的训练或推理运行 `pending/running` 必须转为 `interrupted`；遗留的网格 `pending/running` 必须转为 `incomplete`。不得自动视为成功。

### 3.2 时间与终态不变量

- 所有记录都有 `created_at`。
- `started_at/finished_at` 只约束具有生命周期的完整性、训练拆分、训练运行、推理运行和网格导出记录：尚未实际执行时 `started_at` 为 `null`，进入 `running` 后必须非空；非终态的 `finished_at` 为 `null`，终态必须非空。预检阶段直接失败允许 `started_at` 为 `null`。
- 不可变的推理阶段事件使用 `created_at` 和事件发生时的 `timestamp`，不要求 `started_at/finished_at`；阶段耗时记录在终态事件的 `duration_ms`。
- `succeeded`、`verified` 和 `complete` 必须 `error: null`，且所有必需引用、hash 和 artifact 已复核。
- `pending`、`running`、`started` 和 `skipped` 必须 `error: null`；`skipped` 的原因必须写入稳定的 `decision.reason_code`。
- `failed`、`interrupted`、`incomplete`、`mismatch` 和 `missing` 必须具有非空 `error`。`cancelled` 使用 `error.code: "user_cancelled"` 或等价稳定代码。
- 完成终态不可原地改写。重新训练、重新导出或对已完成文件重新校验时创建新 ID，并用 `retry_of`、`recheck_of` 或 `supersedes` 关联旧记录。

## 4. 文件完整性清单

Schema：`taxamask_integrity_manifest_v1`

权威位置：项目 SQLite 的完整性清单及文件条目。项目尚未打开时，已知的失败事实保存在全局训练台账 SQLite。

下面的 JSON 只展示一份完整性清单的逻辑字段；如实现提供 `runs/<run_kind>/<run_id>/integrity_manifest.json` 供人工查看，它必须是可由 SQLite 重建的只读投影，不参与状态恢复。

```json
{
  "schema_version": "taxamask_integrity_manifest_v1",
  "manifest_id": "integrity_20260718T073000123456Z_a1b2c3d4",
  "run_id": "train_20260718T073000123456Z_7f3a2c1d",
  "status": "verified",
  "created_at": "2026-07-18T15:29:50+08:00",
  "started_at": "2026-07-18T15:29:51+08:00",
  "finished_at": "2026-07-18T15:30:00+08:00",
  "attempt": 1,
  "retry_of": null,
  "files": [
    {
      "file_id": "manual_truth_head",
      "role": "manual_truth",
      "path_base": "project_root",
      "relative_path": "specimens/ANTSCAN_0001/labels/manual_truth.ome.zarr",
      "entry_kind": "directory",
      "size_bytes": 123456,
      "mtime_ns": 1784369400000000000,
      "hash_algorithm": "sha256-tree-v1",
      "digest": "1111111111111111111111111111111111111111111111111111111111111111",
      "status": "verified",
      "verified_at": "2026-07-18T15:30:00+08:00",
      "data_version_id": "data_v0003",
      "error": null
    }
  ],
  "error": null
}
```

允许的 `role` 至少包括 `source_volume`、`training_image`、`manual_truth`、`label_schema`、`training_config`、`initial_weights`、`output_weights` 和 `model_manifest`。

大型原始 CT 可以使用快速指纹做日常复核，但人工标签、实际训练配置、初始模型权重和训练完成后的输出权重必须使用完整 SHA256；目录使用 `sha256-tree-v1`。快速指纹不满足归档完成验收。

`files[]` 中每个条目除 2.4 节字段外，必须包含 `status`、`verified_at`、`data_version_id` 和 `error`。允许状态与完整性清单相同：`pending`、`verified`、`mismatch`、`missing`、`incomplete`；允许转换为 `pending -> verified/mismatch/missing/incomplete`，以及同一次中断校验恢复时的 `incomplete -> pending`。`pending/verified` 的 `error` 为 `null`，其余状态按 2.5 节记录错误；`pending/incomplete/missing` 可将尚不可得的 size、算法、digest 或验证时间保存为 `null`，`verified/mismatch` 必须保存实际观察到的 size、算法和 digest。

清单只有在全部必需文件均为 `verified` 时才能为 `verified`。任一文件为 `mismatch` 时清单为 `mismatch`；没有 mismatch 但存在 `missing` 时为 `missing`；仍有 `pending/incomplete` 或校验过程被取消时为 `incomplete`。不得用顶层成功状态掩盖逐文件异常。

## 5. 训练实际拆分清单

Schema：`taxamask_training_split_v1`

权威位置：项目 SQLite 的训练拆分记录及样本分配条目。

该记录保存实际进入训练和验证的数据，而不是只记录“80/20”或 UI 计划值。外部 backend 必须回传最终 case 分配；无法证明实际分配时训练不得标为 `succeeded`。下面的 JSON 只展示逻辑字段；如生成 `runs/train/<run_id>/split_manifest.json`，它只是 SQLite 的可重建只读投影。

```json
{
  "schema_version": "taxamask_training_split_v1",
  "split_id": "split_20260718T073000223456Z_b2c3d4e5",
  "run_id": "train_20260718T073000123456Z_7f3a2c1d",
  "status": "verified",
  "created_at": "2026-07-18T15:30:00+08:00",
  "started_at": "2026-07-18T15:30:00+08:00",
  "finished_at": "2026-07-18T15:30:01+08:00",
  "dataset_id": "dataset_brain_v0003",
  "strategy": {
    "name": "nnunet_fold",
    "version": "v1",
    "seed": 42,
    "validation_ratio": 0.2
  },
  "assignments": [
    {
      "sample_id": "ANTSCAN_0001",
      "partition": "train",
      "group_id": "ANTSCAN_0001",
      "input_file_ids": ["volume_ANTSCAN_0001", "manual_truth_ANTSCAN_0001"]
    },
    {
      "sample_id": "ANTSCAN_0002",
      "partition": "validation",
      "group_id": "ANTSCAN_0002",
      "input_file_ids": ["volume_ANTSCAN_0002", "manual_truth_ANTSCAN_0002"]
    }
  ],
  "error": null
}
```

`partition` 至少支持 `train`、`validation` 和 `test`。同一 `group_id` 只能属于一个 partition，不能出现在 train/validation、train/test 或 validation/test 的任意组合中；同一标本的切片、视图、reslice 或派生样本必须共享 group_id。限制样本数、过滤空标签或后端再次剔除 case 后，必须保存最终 assignments，并在写入 `verified` 前执行分组泄漏检查。

## 6. 训练运行记录

Schema：`taxamask_training_run_v1`

权威位置：项目已加载后使用项目 SQLite 的 training run 台账。必须先打开项目或外部数据的无界面入口，在解析到项目 SQLite 前先在全局训练台账 SQLite 建立 `pending`；项目加载成功后通过同一稳定 `run_id` 建立项目关联，加载失败也必须在全局 SQLite 收敛为失败终态。不得创建第二份平级事实记录。

下面的 JSON 只展示一条 training run 的逻辑字段；如为人工检查导出 `runs/train/<run_id>/training_run.json` 或运行摘要，它只能是可由 SQLite 重建的只读投影，不参与状态恢复。

```json
{
  "schema_version": "taxamask_training_run_v1",
  "run_id": "train_20260718T073000123456Z_7f3a2c1d",
  "status": "succeeded",
  "entrypoint": "tif_external_nnunet",
  "created_at": "2026-07-18T15:29:50+08:00",
  "started_at": "2026-07-18T15:30:00+08:00",
  "finished_at": "2026-07-18T16:10:00+08:00",
  "retry_of": null,
  "project_ref": {
    "project_kind": "taxamask_tif",
    "project_id": "project_antscan_brain",
    "project_data_version_id": "project_data_v0003"
  },
  "dataset_ref": {
    "dataset_id": "dataset_brain_v0003",
    "data_version_id": "data_v0003",
    "trusted_label_policy": "manual_truth_only"
  },
  "integrity_manifest": {
    "manifest_id": "integrity_20260718T073000123456Z_a1b2c3d4",
    "artifact_id": "integrity_manifest",
    "role": "integrity_manifest",
    "path_base": "run_root",
    "relative_path": "integrity_manifest.json",
    "entry_kind": "file",
    "size_bytes": 2048,
    "hash_algorithm": "sha256",
    "digest": "2222222222222222222222222222222222222222222222222222222222222222"
  },
  "split_manifest": {
    "split_id": "split_20260718T073000223456Z_b2c3d4e5",
    "artifact_id": "split_manifest",
    "role": "training_split",
    "path_base": "run_root",
    "relative_path": "split_manifest.json",
    "entry_kind": "file",
    "size_bytes": 1536,
    "hash_algorithm": "sha256",
    "digest": "3333333333333333333333333333333333333333333333333333333333333333"
  },
  "effective_config": {
    "epochs": 100,
    "batch_size": 2,
    "learning_rate": 0.0001,
    "weight_decay": 0.00001,
    "input_resolution": [512, 512],
    "random_seed": 42,
    "model": {"family": "nnunet", "version": "v2"},
    "loss_weights": {}
  },
  "backend": {
    "backend_id": "nnunet_v2_preset",
    "backend_version": "2.x",
    "adapter_id": "taxamask_tif_nnunet_v2",
    "adapter_version": "1"
  },
  "code": {
    "taxamask_version": "fifth-round-development",
    "revision": "example-local-revision",
    "working_tree_dirty": false
  },
  "environment": {
    "platform": "windows",
    "python": "3.x",
    "pytorch": "2.x",
    "cuda": "not_recorded",
    "compute_device": "cuda:0"
  },
  "note_ref": "project_note_train_20260718_153000",
  "artifacts": [
    {
      "artifact_id": "model_manifest",
      "role": "model_manifest",
      "path_base": "run_root",
      "relative_path": "outputs/model_manifest.json",
      "entry_kind": "file",
      "size_bytes": 4096,
      "hash_algorithm": "sha256",
      "digest": "4444444444444444444444444444444444444444444444444444444444444444",
      "media_type": "application/json"
    },
    {
      "artifact_id": "best_checkpoint",
      "role": "output_weights",
      "path_base": "managed_model_root",
      "relative_path": "nnunet/project_antscan_brain/best.pt",
      "entry_kind": "file",
      "size_bytes": 1048576,
      "hash_algorithm": "sha256",
      "digest": "5555555555555555555555555555555555555555555555555555555555555555",
      "media_type": "application/octet-stream"
    }
  ],
  "error": null
}
```

规则：

- `entrypoint` 使用训练入口矩阵中的稳定标识，包括 GUI、headless 和实验 CLI。
- `project_ref` 为必需对象。无界面入口在 CLI 参数解析后、打开项目或数据集前建立 `pending`，此时使用 `project_kind: "unresolved_project"`、`project_id: null`、`project_data_version_id: null`、`resolution_status: "pending"` 和不透明的 `location_ref`；归档记录不得保存 CLI 原始绝对路径。项目加载成功后，在该记录仍为 `pending` 时将其替换为已解析的项目 ID 和数据版本；加载失败时保留空 ID，将 `resolution_status` 改为 `failed` 并写入脱敏错误。
- `location_ref` 只引用本机位置注册表，不得包含路径、盘符、用户名或可反推私人路径的文本。运行日志根不可写时必须在创建训练进程、DataLoader 或权重前明确失败，不能无记录继续训练。
- 外部数据训练使用 `project_kind: "external_dataset"`、`project_id: null`，但仍必须提供稳定 `dataset_id`、data version、可信来源声明和完整性清单。
- 所有顶层字段在 `pending` 时就必须存在；尚未解析的 `dataset_ref`、`integrity_manifest`、`split_manifest`、`effective_config`、`backend`、`environment` 和 `note_ref` 可为 `null`。失败终态保留当时已知值和空值；`succeeded` 不得保留这些必需事实的空值。
- `effective_config` 保存程序或后端解析后的实际值，不只复制界面输入、CLI 原文或 `backend_default`。
- `split_manifest` 保存最终实际样本分配；只有策略名、fold、比例或随机种子不够。
- `code.revision` 保存可识别当前 TaxaMask 代码的 revision；`backend` 保存后端和适配器的 ID/version。工作区有未提交修改时必须记录 `working_tree_dirty: true`，但不归档完整 diff。
- 所有入口使用同一事实字段，不得因“临时训练”“实验 CLI”省略字段。
- 失败、取消和中断运行也保存当时已知的项目/数据集引用、配置、输入清单引用、拆分进度、终态和脱敏错误。
- 备注可以后续编辑，但配置、清单、状态时间和 artifact 事实不可被备注写回覆盖。

## 7. 推理运行与分阶段事件

### 7.1 推理运行

Schema：`taxamask_inference_run_v1`

建议位置：`TaxaMask_outputs/runtime_logs/inference_runs/<run_id>/inference_run.json`

推理 run 是阶段事件的生命周期承载记录。每个 `taxamask_inference_event_v1.run_id` 必须引用一个已建立的 inference run；程序崩溃后由恢复检查把遗留 run 收敛到 `interrupted`，不修改此前已完成的事件。

```json
{
  "schema_version": "taxamask_inference_run_v1",
  "run_id": "infer_20260718T090000023456Z_9a8b7c6d",
  "status": "interrupted",
  "entrypoint": "predict_full_pipeline",
  "created_at": "2026-07-18T16:59:59+08:00",
  "started_at": "2026-07-18T17:00:00+08:00",
  "finished_at": "2026-07-18T17:00:01+08:00",
  "project_ref": {
    "project_kind": "taxamask_2d",
    "project_id": "project_antscan_images"
  },
  "input_ref": {
    "image_id": "image_0001",
    "data_version_id": "image_data_v0004"
  },
  "event_log": {
    "artifact_id": "inference_event_log",
    "role": "inference_events",
    "path_base": "runtime_log_root",
    "relative_path": "inference_runs/infer_20260718T090000023456Z_9a8b7c6d/events.jsonl",
    "entry_kind": "file",
    "size_bytes": 3072,
    "hash_algorithm": "sha256",
    "digest": "9999999999999999999999999999999999999999999999999999999999999999"
  },
  "last_complete_sequence": 4,
  "error": {
    "code": "process_interrupted",
    "summary": "The application stopped before the inference run reached a terminal event.",
    "stage": "recovery_check",
    "recoverable": true,
    "diagnostic_artifact_id": "inference_event_log"
  }
}
```

`succeeded` 要求所有必需阶段均有终态事件且 `error: null`；`failed/cancelled/interrupted` 必须保留最后完整事件序号和脱敏错误。JSONL 最后一行损坏时，run 仍引用前面可解析的事件并记录 `last_complete_sequence`。

### 7.2 分阶段事件

Schema：`taxamask_inference_event_v1`

存储位置：复用现有 `TaxaMask_outputs/runtime_logs/`，以结构化 JSONL 事件记录；不建立第二套日志系统。

```json
{
  "schema_version": "taxamask_inference_event_v1",
  "event_id": "event_20260718T090000123456Z_c3d4e5f6",
  "run_id": "infer_20260718T090000023456Z_9a8b7c6d",
  "stage_span_id": "span_locator_image_0001",
  "sequence": 2,
  "status": "succeeded",
  "stage": "locator",
  "created_at": "2026-07-18T17:00:00+08:00",
  "timestamp": "2026-07-18T17:00:00+08:00",
  "image_ref": "image_0001",
  "specimen_ref": null,
  "part": "Head",
  "model": {"model_id": "locator/base", "model_version": "v4"},
  "input_summary": {"width": 2048, "height": 1536},
  "thresholds": {"peak": 0.35},
  "decision": {"candidate_found": true, "reason_code": "peak_above_threshold"},
  "output_summary": {"candidate_count": 1, "max_score": 0.91},
  "duration_ms": 18.4,
  "error": null
}
```

每个事件的 `run_id` 必须引用 `taxamask_inference_run_v1`。阶段名至少支持 `input`、`locator`、`crop`、`expert_route`、`sam` 和 `assemble`。`skipped` 必须具有稳定 `decision.reason_code`；`failed` 必须具有非空 `error`。

同一 run 的 `sequence` 从 1 开始，是无空洞、严格递增且唯一的正整数；事件只能按 sequence 追加。每次阶段尝试生成一个在该 run 内唯一的 `stage_span_id`，该 ID 只能由同一阶段的一条 `started` 事件和至多一条终态事件共享，不能被另一阶段或重试复用。终态事件必须位于对应 `started` 之后。

`last_complete_sequence` 是最后一条以换行结束、可解析、schema 合法且满足上述连续性规则的事件序号。仅允许忽略一个损坏的末尾行；在完整行中发现重复、空洞、倒序、span 冲突或 started/终态不配对时，必须停止恢复并把 run 标为 `interrupted`，写出诊断，不能静默跳过后续事件。

默认事件只能保存尺寸、阈值、框/分数摘要、原因码和耗时，不保存原图、完整 mask、完整 polygon 点列或大数组。JSONL 末尾若因崩溃出现不完整行，读取器忽略该行并把对应 run 标记为中断，不得破坏此前完整事件。

## 8. 网格导出 SQLite 记录

逻辑 schema：`taxamask_mesh_export_sqlite_v1`

位置：项目 SQLite。导出目录只默认包含 STL 和可选诊断产物，不生成 `mesh_export_manifest.json`。

SQLite export run 必须直接保存“导出当时实际读取的 manual truth”的完整哈希；不得只引用某次旧训练的完整性清单，也不得假设 data version 未变化。下面的 JSON 形状只用于在文档中展示一条逻辑记录，不对应磁盘 JSON 文件。

```json
{
  "schema_version": "taxamask_mesh_export_sqlite_v1",
  "export_id": "mesh_20260718T100000123456Z_d4e5f6a7",
  "status": "complete",
  "created_at": "2026-07-18T17:59:50+08:00",
  "started_at": "2026-07-18T18:00:00+08:00",
  "finished_at": "2026-07-18T18:00:10+08:00",
  "retry_of": null,
  "project_ref": {
    "project_kind": "taxamask_tif",
    "project_id": "project_antscan_brain"
  },
  "source": {
    "file_id": "manual_truth_ANTSCAN_0001_data_v0003",
    "role": "manual_truth",
    "specimen_id": "ANTSCAN_0001",
    "label_role": "manual_truth",
    "data_version_id": "data_v0003",
    "integrity_manifest_id": "integrity_20260718T095959123456Z_e5f6a7b8",
    "path_base": "project_root",
    "relative_path": "specimens/ANTSCAN_0001/labels/manual_truth.ome.zarr",
    "entry_kind": "directory",
    "size_bytes": 123456,
    "hash_algorithm": "sha256-tree-v1",
    "digest": "6666666666666666666666666666666666666666666666666666666666666666",
    "hashed_at": "2026-07-18T17:59:59+08:00"
  },
  "coordinates": {
    "source_axis_order": "zyx",
    "mesh_axis_order": "xyz",
    "spacing_zyx": [2.0, 2.0, 2.0],
    "spacing_unit": "micrometer",
    "output_unit": "millimeter",
    "axis_transform": [[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0], [0, 0, 0, 1]],
    "scale_status": "verified"
  },
  "meshes": [
    {
      "artifact_id": "raw_structure_a",
      "role": "mesh",
      "label_id": 1,
      "label_name": "structure_a",
      "kind": "raw",
      "path_base": "export_root",
      "relative_path": "raw/ANTSCAN_0001_structure_a.stl",
      "entry_kind": "file",
      "size_bytes": 98765,
      "hash_algorithm": "sha256",
      "digest": "7777777777777777777777777777777777777777777777777777777777777777",
      "vertex_count": 1200,
      "face_count": 2396,
      "bounds_xyz_mm": [[0.0, 0.0, 0.0], [1.2, 0.8, 0.6]],
      "component_count": 1,
      "watertight": false,
      "processing": {"smoothed": false, "filled_holes": false, "removed_components": false}
    }
  ],
  "error": null
}
```

本轮只要求 STL。OBJ/PLY 不属于交付或验收范围。原始网格不得平滑、补洞或删除小结构；展示副本必须使用 `kind: "preview"`，另存为独立 artifact，并在 SQLite 中完整记录平滑、补洞、组件处理及参数。Blender 5.0 验收使用项目界面对 SQLite 记录的只读展示来核对单位、轴顺序和变换。

### 8.1 SQLite run/item 字段

SQLite 中的逻辑记录至少保存：

```text
export_id / retry_of
status / attempt
project_ref / specimen_ref / source_data_version_id
target_location_ref / target_path_base / target_relative_path
record_schema_version / stl_item_count / completed_item_count
source_size_bytes / source_hash_algorithm / source_digest
created_at / started_at / finished_at
error_code / error_summary / error_stage / recoverable
recovery_action
```

`target_location_ref` 是本机位置注册表中的不透明 ID；项目 SQLite 和诊断产物都不保存目标绝对路径。位置注册丢失时 export 进入 `incomplete`，提示用户重新定位同一目录并复核 SQLite 所列 STL 哈希。

SQLite 是网格导出的唯一状态、对账和恢复来源，默认不生成网格 JSON。若未来另行设计用户显式触发的一次性只读交换报告，它也只能复制已完成 SQLite 记录，不能恢复、覆盖或替代项目状态。

SQLite 事务不能覆盖外部文件系统。完成状态必须依次复核：

1. SQLite export run/item 的 schema、`export_id`、状态和相对路径合法；
2. 导出时源标签的完整哈希字段存在且复验匹配；
3. 所有正式 STL 存在，size、算法和 digest 与 SQLite item 匹配；
4. 单位、轴向、处理参数和网格质量字段完整；
5. 以上全部通过后才在一个 SQLite 事务中写 `complete`。

任一步失败都进入 `incomplete` 或 `failed`，并保留继续校验、重试、查看诊断、安全清理或重新定位目录入口。

中断收敛规则：

- STL 临时文件或正式文件已写，但 SQLite 尚未完成：保持 `incomplete`。启动时按 SQLite 预登记的相对路径和预期摘要复验；一致时可完成原子发布并在单个事务中收敛为 `complete`，否则提供重试或列明文件后的安全清理。
- SQLite 已预登记 item，但 STL 缺失、越界或摘要不符：保持 `incomplete`，记录具体文件和错误；不得自动接受当前磁盘内容为新基线。
- 已完成导出在以后复核时发现 STL 缺失或摘要不符：保留原始完成记录作为历史事实，追加 `needs_attention` 复核记录，并在界面停止把该导出显示为当前可验证产物；不得自动覆盖用户文件。
- SQLite 终态提交成功后程序崩溃：下次启动仍按 SQLite 记录复验全部 STL。复验通过保持可用；失败按上一条追加异常复核记录。

本轮不实现网格交换 JSON。以后若因论文附件或跨机构交换另行批准只读报告，必须在 SQLite `complete` 后显式生成，损坏时只能由 SQLite 重新导出，且不参与本节完成判定或中断恢复。

## 9. 向后兼容与变更规则

- v1 读取器必须拒绝把未知 major schema 当成已验证或完成记录。
- 同一 v1 内只能新增可选字段；读取器忽略未知可选字段，但缺少本契约的必需字段时拒绝完成状态。
- 改变字段含义、状态词、路径基准、哈希语义或新增必需字段必须发布新 major schema，并提供显式迁移/只读兼容测试。
- 已完成记录不可原地改写；重试、复核和替代记录使用 `retry_of`、`recheck_of` 或 `supersedes`。
- 旧 TIF/Local Axis/backend manifest 保持原 schema，由 adapter 映射到统一记录；不得因为旧状态名为 `success` 或路径为绝对路径就直接复制为已验证事实。
- 契约变化必须同时更新自动测试、小型示例、训练入口矩阵和第五轮需求追踪记录。

## 10. 第一阶段验收检查

- 完整性、拆分、训练、推理 run/事件和网格记录都有稳定 ID、状态、时间及统一 error 规则。
- 所有受管 artifact 和文件引用都使用白名单 path base、严格相对路径、size、算法和 digest；无法复制的外部产物只使用可复验且不含私人路径的 `external_reference`。
- 训练记录能够关联项目、数据版本、实际 split、代码 revision、backend/adapter、环境、备注和全部产物。
- 推理 run 能承载成功、失败、取消和崩溃中断；阶段事件能表达开始、成功、跳过和失败，且默认不泄漏大数据或敏感配置。
- 网格来源、尺度、处理参数、STL 哈希和恢复状态只以 SQLite 为权威；默认不生成网格 JSON sidecar。
- 所有示例均使用虚构相对路径、ID 和摘要，不包含真实研究数据或本机绝对路径。
