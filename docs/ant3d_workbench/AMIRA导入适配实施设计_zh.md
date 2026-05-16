# AMIRA 导入适配实施设计

> 所属方向：Ant 3D Workbench / TIF Volume Mode
>
> 目标：把现有 AMIRA/Avizo 标注数据只读导入 Ant 3D Workbench，并转换为开放、可编辑、可训练的 TIF Project 数据层。

## 1. 样例数据边界

当前第一阶段以用户提供的真实样例目录为适配目标：

```text
D:\confirm-project\LBJ-workspace\new-project\AMIRA-data
```

样例包含：

```text
raw .tif
.hx
.resampled
.labels
.MaterialStatistics
.surf
decode_log.txt
visualize_labels.py
```

已确认的关键点：

- raw `.tif` 是原始来源数据。
- `.hx` 是 AMIRA/Avizo 项目文件，用于判断数据连接关系。
- `.labels` 是 label field，每个体素保存 material ID。
- `.resampled` 是与 `.labels` 对齐的 working image volume。
- 当前样例不能直接把 `.labels` 叠加到 raw `.tif` 上，因为 shape 可能不同。
- `.surf` 是 AMIRA 派生 surface，不作为第一阶段核心训练真值。

## 2. 适配目标

导入器要完成：

- 读取 AMIRA 项目中的 label material 定义；
- 识别 `.labels` 对齐的 image volume；
- 保留 raw TIF 作为 source/provenance；
- 将 `.resampled` 转成 `working/image.ome.zarr/`；
- 将 `.labels` 转成 `labels/manual_truth.ome.zarr/`；
- 生成 `material_map.json`；
- 生成 `import_report.json`；
- 在 `project.json` 中登记 specimen、路径、shape、状态和来源。

导入器第一阶段不做：

- 不修改 AMIRA 原始文件；
- 不写回 `.labels`；
- 不承诺兼容所有 AMIRA 项目变体；
- 不把 `.surf` 当作训练真值；
- 不强行把 raw TIF resize 到 label shape。

## 3. 导入流程

```text
选择 AMIRA 数据目录
-> 扫描文件
-> 解析 .hx
-> 找到 label field 和对齐的 working volume
-> 解析 .labels header 与 material
-> 解码 label 数据
-> 读取 .resampled / raw TIF metadata
-> 检查 shape 和 alignment
-> 写入 OME-Zarr sidecar
-> 生成 material_map.json
-> 生成 import_report.json
-> 更新 project.json
```

## 4. 文件扫描规则

第一阶段按目录内文件后缀识别：

- `*.tif` 或 `*.tiff`：raw source TIF；
- `*.hx`：AMIRA 项目文件；
- `*.labels`：AMIRA label field；
- `*.resampled`：AMIRA 对齐后的 working volume；
- `*.MaterialStatistics`：material 统计信息；
- `*.surf`：AMIRA surface 派生产物。

如果同类文件有多个：

- 先让导入器列出候选；
- 优先使用 `.hx` 中引用的文件；
- 如果 `.hx` 无法解析，要求用户手动选择。

## 5. `.hx` 解析

它是什么：

- AMIRA/Avizo 的项目描述文件。
- 里面通常包含数据节点、连接关系和文件引用。

为什么解析：

- 不能只靠文件名猜测 `.labels` 应该叠加在哪个图像 volume 上。
- 当前样例里 `.labels` 对齐 `.resampled`，不是 raw `.tif`。

需要提取：

- label field 文件路径；
- image volume 文件路径；
- label 与 image 的连接关系；
- 可能存在的 spacing、bounding box、transform 信息。

影响流程：

- 决定 overlay 是否正确；
- 决定训练导出的 image/label 是否匹配；
- 决定 raw TIF 是否只是 provenance。

如果无法解析：

- 不应静默导入；
- 应生成 warning；
- 要求用户手动确认 image volume 和 label volume 的配对。

## 6. `.labels` 解析

它是什么：

- AMIRA label field 文件。
- Header 中保存 lattice 尺寸、数据类型、材料定义等信息。
- Binary 区域保存每个体素的 material ID。

第一阶段需要解析：

- AmiraMesh 版本；
- endian；
- lattice shape；
- data type；
- encoding，例如 HxByteRLE；
- material names；
- material colors，如果 header 中可获得；
- binary data offset。

样例中已观察到：

```text
# AmiraMesh BINARY-LITTLE-ENDIAN 3.0
define Lattice 1225 1218 231
```

注意：

- AMIRA header 通常以 X/Y/Z 顺序描述 lattice。
- 程序内部建议统一使用 Z/Y/X。
- 因此导入时要明确记录 shape 转换，不要靠猜。

## 7. RLE 解码策略

当前样例里的 `.labels` 可能使用 HxByteRLE。

第一阶段实现建议：

- 先从 header 判断 encoding；
- 对支持的 encoding 执行解码；
- 解码后检查体素数量是否等于 `X * Y * Z`；
- reshape 时明确从 AMIRA lattice 转成内部 `shape_zyx`；
- 解码失败时保留错误日志，不生成半成品 `manual_truth`。

为什么重要：

- label 体素一旦错位，训练会直接学坏。
- 脑区分区这类数据必须保证每个 material 的空间位置正确。

对研究流程的影响：

- 成功导入后，旧共聚焦 AMIRA 数据可以成为第一批训练真值。
- 失败时用户可以把日志交给智能体或开发者继续适配。

## 8. `.resampled` 读取

它是什么：

- AMIRA 处理后与 label 对齐的 image volume。

为什么优先读取：

- 当前样例中 `.labels` 是和 `.resampled` 对齐，不是和 raw `.tif` 对齐。

影响流程：

- TIF 工作台显示的原图 slice 应该来自 `.resampled` 转换后的 `working/image.ome.zarr/`。
- raw `.tif` 作为 source/provenance 保存。

如果 `.resampled` 无法读取：

- 不应把 `.labels` 强行叠加到 raw TIF；
- 应提示用户需要手动确认对齐 volume。

## 9. Shape 检查

导入器必须记录并检查：

- raw TIF shape；
- resampled volume shape；
- labels shape；
- internal working shape；
- final label shape。

判断规则：

- `resampled shape == labels shape`：可作为对齐组合导入。
- `raw TIF shape != labels shape`：允许，但必须记录 warning。
- `resampled shape != labels shape`：默认阻断导入，除非用户明确手动确认。

为什么重要：

- shape 不一致不一定是错误，可能是 AMIRA resampling 的正常结果。
- 但 label 和 working image 不一致会直接导致 overlay 错位。

## 10. Material map 生成

AMIRA material 要转换成本项目的 `material_map.json`。

规则：

- 尽量保留 AMIRA 原始 material ID；
- 原始名称写入 `source_name`；
- 界面显示名称写入 `display_name`；
- 如果 AMIRA 有颜色，优先使用原颜色；
- 如果没有颜色，按稳定规则生成颜色；
- `0` 默认作为 background，`trainable: false`；
- 其他 material 默认 `trainable: true`，但用户后续可以修改。

输出示例：

```json
{
  "schema_version": "ant3d_tif_material_map_v1",
  "source": "amira_import_adapter_v1",
  "materials": [
    {
      "id": 0,
      "name": "background",
      "display_name": "Background",
      "color": "#000000",
      "trainable": false,
      "source_name": "Exterior"
    },
    {
      "id": 1,
      "name": "LO_L",
      "display_name": "LO_L",
      "color": "#f94144",
      "trainable": true,
      "source_name": "LO_L"
    }
  ]
}
```

## 11. `import_report.json`

每次导入必须生成报告。

它是什么：

- 导入过程的审计记录。

为什么保存：

- 用户需要知道这份 working volume 和 label 是怎么来的。
- 后续训练出现问题时，可以回看导入时有没有 shape warning。

建议字段：

```json
{
  "schema_version": "ant3d_amira_import_report_v1",
  "imported_at": "2026-05-15T15:30:00+08:00",
  "adapter_version": "amira_import_adapter_v1",
  "source_dir": "D:/confirm-project/LBJ-workspace/new-project/AMIRA-data",
  "files": {
    "raw_tif": "20.02.2022 NO.2 gyne pupa brain-3_2.tif",
    "hx": "20.02.2022 NO.2 gyne pupa brain-3_4(1).hx",
    "resampled": "20.02.2022-NO.2-gyne-pupa-brain-3_20.02.2022-NO.resampled",
    "labels": "20.02.2022-NO.2-gyne-pupa-brain-3_20.02.2022-NO(1).labels"
  },
  "shapes": {
    "raw_tif_zyx": [280, 1960, 1939],
    "resampled_zyx": [231, 1218, 1225],
    "labels_zyx": [231, 1218, 1225]
  },
  "alignment": {
    "working_image": "resampled",
    "labels_aligned_to": "resampled",
    "raw_tif_used_as": "source_provenance"
  },
  "materials": {
    "count": 12,
    "source": "labels_header"
  },
  "warnings": [
    "raw_tif_shape_differs_from_labels_shape"
  ],
  "errors": []
}
```

## 12. 导入到 TIF Project 的结果

成功导入后，项目中应出现：

```text
specimens/<specimen_id>/source/raw/original.tif
specimens/<specimen_id>/source/amira_original/project.hx
specimens/<specimen_id>/source/amira_original/image.resampled
specimens/<specimen_id>/source/amira_original/labels.labels
specimens/<specimen_id>/working/image.ome.zarr/
specimens/<specimen_id>/working/import_report.json
specimens/<specimen_id>/labels/manual_truth.ome.zarr/
specimens/<specimen_id>/labels/working_edit.ome.zarr/
specimens/<specimen_id>/material_map.json
```

其中：

- `manual_truth` 来自 AMIRA 已有人工作业标注；
- `working_edit` 初始可以复制自 `manual_truth`；
- 后续用户修改保存时不改变 AMIRA 原始 `.labels`。

## 13. UI 提示

导入完成后，界面应让用户看到：

- specimen 编号；
- raw TIF shape；
- working volume shape；
- label shape；
- material 数量；
- 是否有 shape mismatch；
- 使用的是 raw TIF 还是 resampled 作为显示底图；
- 是否已经生成 manual truth。

为什么重要：

- 用户不需要懂 AMIRA 文件细节，也能判断导入是否可信。

## 14. 错误处理

必须阻断的错误：

- 找不到 `.labels`；
- label 数据解码失败；
- label 解码后体素数不匹配；
- working image 与 label shape 不一致且用户未确认；
- material map 为空或无法生成。

允许继续但要 warning 的情况：

- raw TIF 与 label shape 不一致；
- `.surf` 缺失；
- `.MaterialStatistics` 缺失；
- spacing/orientation 缺失；
- 部分 material 没有颜色。

## 15. 第一阶段验收标准

- 可以从样例 AMIRA 目录导入一个 specimen；
- 可以正确识别 `.resampled + .labels` 是对齐组合；
- raw `.tif` 被保存或登记为 source/provenance；
- 可以生成 `working/image.ome.zarr/`；
- 可以生成 `manual_truth.ome.zarr/`；
- 可以生成 `material_map.json`；
- 可以生成 `import_report.json`；
- 导入结果能被 TIF slice viewer 打开并叠加显示；
- 原始 AMIRA 文件没有被修改。
