# Ant 3D Workbench 阶段实施与复核计划

> 所属方向：Ant 3D Workbench / 超长实施任务
>
> 目标：把 `docs/ant3d_workbench` 中的需求和实施设计转成可连续编码、可阶段复核、可暂停恢复的执行计划。

## 1. 文档用途

这份文档不是新的产品需求，而是后续超长编码任务的执行约定。

它回答三个问题：

- 每个大阶段应该实现什么；
- 每个阶段通过前必须检查什么；
- 哪些边界不能在编码过程中被悄悄扩大。

执行方式建议为：

```text
用户确认本计划
-> 开始阶段 0
-> 阶段完成后进行严格复核
-> 用户确认或要求修改
-> 通过后进入下一阶段
-> 重复直到所有阶段完成
-> 最后做总体验收和汇报
```

除非用户明确要求，编码阶段不应把每个小改动都同步到根目录 `CHANGELOG_zh.md` 或 `LLM_CONTEXT_DETAILED.md`。只有当某个阶段改变了实际可操作流程、项目格式或安全边界时，才建议在阶段收口时同步长期上下文。

## 2. 总体实施原则

### 2.1 面向研究流程，而不只是面向代码结构

每个阶段复核时都要说明：

- 程序现在能做什么；
- 这对 STL/TIF/AMIRA 标注、复核、训练或预测有什么实际意义；
- 对用户已有数据安全有什么影响；
- 下一阶段继续开发前还剩哪些风险。

### 2.2 TIF 与 STL/2D 保持独立

TIF Volume Mode 是独立项目类型，不应塞进现有 2D/STL 项目 JSON。

第一阶段原则：

- 旧 TaxaMask / STL-derived 2D 项目继续由现有 `ProjectManager`、Labeling Workbench、Blink、Locator/SAM 处理；
- 新 TIF project 使用独立 schema、独立项目管理、独立 UI、独立后端契约；
- TIF label/material map 不和 STL taxonomy / locator scope 混用；
- TIF 后端不复用现有 polygon/box 外部后端契约。

### 2.3 人工真值优先

强约束：

- `manual_truth` 是人工确认后的训练真值；
- `model_draft` 只是模型粗标；
- `working_edit` 是用户正在修正的编辑层；
- 模型预测不得默认覆盖 `manual_truth`；
- 训练默认只读取 `manual_truth`，不默认读取 `model_draft`；
- 从 `model_draft` 进入训练真值必须经过用户明确接受或人工复核流程。

### 2.4 AMIRA 原始文件只读

第一阶段 AMIRA 兼容目标是读取和转换，不是写回。

不得做的事：

- 不修改 raw `.tif`；
- 不修改 `.hx`；
- 不修改 `.labels`；
- 不写回 AMIRA 原生 label field；
- 不把 `.surf` 当成第一阶段训练真值；
- 不在 shape 不匹配时静默叠加 label。

### 2.5 阶段复核优先于连续堆功能

每个大阶段完成后必须暂停进行复核。复核通过前，不进入下一大阶段。

复核不只看测试是否通过，还要检查：

- 数据是否写到预期位置；
- project JSON 是否轻量；
- 大体数据是否在 sidecar；
- 是否存在覆盖人工真值的路径；
- 导入报告和运行报告是否足以追溯；
- UI 文案是否能让非算法背景的分类学研究者理解。

## 3. 阶段总览

建议阶段顺序如下：

```text
阶段 0：实施前基线检查与依赖确认
阶段 1：TIF Project 数据层最小骨架
阶段 2：AMIRA 只读导入最小闭环
阶段 3：TIF slice viewer 与 label overlay
阶段 4：TIF 画笔编辑、擦除、撤销重做与人工确认
阶段 5：TIF backend contract v1 与预测导入 model_draft
阶段 6：主界面入口重排、PDF 下沉、旧项目兼容边界
阶段 7：总体验收、文档同步与最终汇报
```

阶段 1 到阶段 5 是第一轮 TIF 核心闭环。阶段 6 是产品入口整理。阶段 7 是第一轮收口。

核对需求文档后，还需要把“完整需求覆盖”拆出后续补充阶段，见本文第 16 节。否则本计划容易变成只完成 TIF 核心闭环，而遗漏 STL rendered-view 项目轻量迁移、普通 TIF stack 导入、导出适配、PDF 文献证据层和跨项目 specimen 关联等内容。

## 4. 阶段 0：实施前基线检查与依赖确认

### 4.1 目标

在写入核心代码前，确认当前代码基线、测试状态、可新增依赖和真实样例数据路径。

### 4.2 需要确认的输入

用户最好提供或确认：

- AMIRA 样例目录路径；
- 样例中预期 `.labels` shape、`.resampled` shape、raw TIF shape；
- material 数量或至少已知 material 名称示例；
- 是否允许新增依赖，例如 `numpy`、`tifffile`、`zarr`、`ome-zarr`；
- OME-Zarr 第一版是否必须严格完整 NGFF metadata，还是允许先实现可恢复的 Zarr sidecar，再逐步增强 metadata；
- TIF 工作台第一版界面优先级。

### 4.3 实施内容

- 检查 `git status --short`；
- 记录当前未跟踪和用户已有改动，不回滚；
- 运行当前核心测试或至少运行和项目打开、UI smoke、外部后端相关的测试；
- 确认依赖安装方案；
- 建立 `.tmp_validation/` 下的临时验证路径，完成后清理。

### 4.4 验收标准

- 已明确真实 AMIRA 样例路径或暂定用 fixture/mock；
- 已明确依赖边界；
- 已知道当前测试基线是否干净；
- 已列出第一轮编码可能触碰的文件范围；
- 没有修改用户未授权的历史文档或数据文件。

### 4.5 阶段复核问题

- 当前代码基线是否适合开始大改？
- 是否有必须先修的阻断测试？
- AMIRA 样例是否足够支撑导入器开发？
- 依赖选择是否会影响用户安装难度？

## 5. 阶段 1：TIF Project 数据层最小骨架

### 5.1 目标

实现 `ant3d_tif_project_v1` 的独立项目数据层，让程序可以新建、保存、打开、检查 TIF project。

### 5.2 建议实现范围

新增 TIF 专用核心模块，例如：

```text
AntSleap/core/tif_project.py
AntSleap/core/tif_materials.py
AntSleap/core/tif_volume_io.py
```

实际文件名可根据代码风格调整。

核心能力：

- 创建 TIF project 目录；
- 写入轻量 `project.json`；
- 管理 specimen 记录；
- 管理 `working_volume`、`manual_truth`、`working_edit`、`model_drafts` 路径；
- 读取和写入 `material_map.json`；
- 做 train-ready 最小判断；
- 将相对路径解析为项目内路径；
- 保留 schema version。

### 5.3 不在本阶段做

- 不做 AMIRA 解码；
- 不做 UI；
- 不做画笔编辑；
- 不做真实模型后端；
- 不改现有 2D `ProjectManager` 的核心语义。

### 5.4 验收标准

- 可以创建一个最小 TIF project；
- 可以保存并重新打开；
- `project.json` 包含 `schema_version: ant3d_tif_project_v1` 和 `project_type: tif_volume`；
- specimen 记录能保存 source、working volume、labels、material map、review status、train_ready；
- train-ready 检查能识别缺失 image、缺失 label、缺失 material map、shape mismatch；
- 测试覆盖正常项目、缺失文件、shape mismatch、无 trainable material。

### 5.5 研究流程意义

通过本阶段后，TIF 数据不再是散落文件，而是可以按 specimen 编号组织、恢复和审计的项目资产。

### 5.6 阶段复核问题

- project JSON 是否仍然轻量？
- 大 volume 路径是否只作为 sidecar 引用？
- material ID 是否稳定保存？
- TIF 项目是否没有污染旧 2D/STL 项目结构？

## 6. 阶段 2：AMIRA 只读导入最小闭环

### 6.1 目标

实现针对真实样例结构的 AMIRA 只读导入器，把 `.resampled + .labels` 转换为 TIF project 可用的 working volume 和 manual truth。

### 6.2 建议实现范围

新增 AMIRA 适配模块，例如：

```text
AntSleap/core/amira_import.py
```

核心能力：

- 扫描目录中的 `.hx`、`.labels`、`.resampled`、raw `.tif`、`.MaterialStatistics`、`.surf`；
- 解析 `.hx` 中的文件引用和连接关系；
- 解析 `.labels` header；
- 支持样例需要的 label encoding，例如 HxByteRLE；
- 明确 AMIRA lattice X/Y/Z 到内部 Z/Y/X 的转换；
- 读取或转换 `.resampled` 作为 working image；
- raw TIF 作为 source/provenance；
- 生成 `material_map.json`；
- 生成 `import_report.json`；
- 写入 `manual_truth` 和初始 `working_edit`；
- 更新 TIF project specimen 记录。

### 6.3 不在本阶段做

- 不写回 AMIRA；
- 不承诺兼容所有 AMIRA/Avizo 变体；
- 不把 `.surf` 作为训练真值；
- 不在 resampled 和 labels shape 不一致时自动继续；
- 不强行把 raw TIF resize 到 label shape。

### 6.4 验收标准

- 可以从样例目录导入一个 specimen；
- 能识别 `.labels` 对齐的是 `.resampled`；
- raw `.tif` 被保留为 source/provenance；
- label 解码后的体素数等于 `X * Y * Z`；
- 内部 shape 统一记录为 `shape_zyx`；
- `resampled shape == labels shape` 时允许导入；
- `raw TIF shape != labels shape` 时生成 warning，而不是失败；
- `resampled shape != labels shape` 时默认阻断；
- 生成 `import_report.json`，包含 files、shapes、alignment、materials、warnings、errors；
- 原始 AMIRA 文件没有被修改。

### 6.5 研究流程意义

通过本阶段后，已有 AMIRA 共聚焦脑区标注可以安全进入 Ant 3D Workbench，作为后续训练和迁移实验的第一批人工真值。

### 6.6 阶段复核问题

- overlay 对齐依据是否来自 `.hx` 或用户明确确认，而不是文件名猜测？
- shape warning 是否足够清楚？
- material map 是否保留 AMIRA 原始 ID 和名称？
- 失败时是否避免生成半成品训练真值？

## 7. 阶段 3：TIF slice viewer 与 label overlay

### 7.1 目标

新增 TIF Volume Mode 的最小可视化工作台，让用户能按 specimen 打开 volume，逐 slice 查看原图和 label overlay。

### 7.2 建议实现范围

新增 UI 模块，例如：

```text
AntSleap/ui/tif_workbench.py
AntSleap/ui/tif_canvas.py
```

核心能力：

- 左侧按 specimen 显示；
- 显示 specimen review status / train-ready status；
- 中央显示当前 slice；
- 支持 slice 前后切换和 slider；
- 支持 label overlay 半透明叠加；
- 右侧显示 material 列表、颜色、trainable 状态；
- 显示 shape、spacing、modality、import warning；
- 支持亮度、对比度、overlay opacity 调整；
- 打开 TIF project 时进入 TIF 工作台。

### 7.3 不在本阶段做

- 不做画笔编辑；
- 不做模型预测；
- 不做 3D 重建；
- 不做复杂多窗口联动；
- 不把 TIF slice 当作旧 polygon canvas 图片导入。

### 7.4 验收标准

- 打开 TIF project 后能看到 specimen 列表；
- 选择 specimen 后能显示 working volume slice；
- label overlay 与 image shape 一致；
- material 颜色显示稳定；
- opacity/brightness/contrast 调整不会改写数据；
- shape mismatch 或 import warning 能在界面看到；
- 旧 2D/STL 项目仍能按旧方式打开。

### 7.5 研究流程意义

通过本阶段后，用户可以直观看到 AMIRA 导入是否可信，检查脑区 label 是否叠在正确的切片位置上。

### 7.6 阶段复核问题

- 用户是否能不懂 AMIRA header 也判断导入质量？
- UI 是否清楚区分原图、人工真值和模型草稿？
- 大 volume 是否避免一次性全量塞进 UI 内存？
- 旧工作台是否没有被破坏？

## 8. 阶段 4：TIF 画笔编辑、擦除、撤销重做与人工确认

### 8.1 目标

实现 TIF 标注工作的基本人工修正能力，让用户能在 slice 上画 material label，并把复核后的结果提升为 `manual_truth`。

### 8.2 建议实现范围

核心能力：

- 当前 material 选择；
- brush painting；
- Ctrl 或类似修饰键快速 erase；
- brush size 控制；
- undo / redo；
- 保存到 `working_edit`；
- 从 `manual_truth` 复制到 `working_edit`；
- 从 `model_draft` 复制到 `working_edit`；
- 用户明确确认后，将 `working_edit` 提升或更新为 `manual_truth`；
- review status 更新，例如 `in_progress`、`reviewed`、`train_ready`。

### 8.3 不在本阶段做

- 不做复杂智能画笔；
- 不做 3D 连续插值；
- 不做多人协作冲突处理；
- 不做自动质量评分；
- 不让模型草稿一键静默变成训练真值。

### 8.4 验收标准

- brush 修改只影响 `working_edit`；
- undo/redo 在当前编辑会话中可靠；
- erase 能把区域恢复为 background 或指定空标签；
- 保存后重新打开仍能看到编辑结果；
- 提升为 `manual_truth` 前有明确用户动作；
- 已有 `manual_truth` 不会被模型预测默认覆盖；
- train-ready 只在人工确认条件满足时为 true。

### 8.5 研究流程意义

通过本阶段后，模型粗标或 AMIRA 旧标注可以被人工逐 slice 修正，形成可进入训练的可信 label volume。

### 8.6 阶段复核问题

- 每一笔编辑写入的是哪一层？
- 用户误操作是否可以撤销？
- `manual_truth` 更新是否足够明确？
- 训练集是否仍然只基于人工确认结果？

## 9. 阶段 5：TIF backend contract v1 与预测导入 model_draft

### 9.1 目标

实现独立 TIF 后端契约，让外部 volume segmentation 模型可以准备数据、训练、预测，并把预测作为 `model_draft` 导回项目。

### 9.2 建议实现范围

新增 TIF 后端模块，例如：

```text
AntSleap/core/tif_backend.py
```

核心能力：

- 生成 `ant3d_tif_backend_contract_v1`；
- 支持 action：`prepare_dataset`、`train`、`predict`；
- 创建 run directory；
- 写入 contract JSON；
- 执行外部脚本；
- 捕获 stdout/stderr；
- 读取 `ant3d_tif_backend_result_v1`；
- 校验 prediction artifact；
- 将 prediction label volume 导入 `model_draft`；
- 登记 model record 和 run record；
- 强制 `protect_manual_truth: true` 默认开启。

### 9.3 不在本阶段做

- 不内置 nnU-Net；
- 不内置 MONAI；
- 不做自动调参；
- 不做云端训练；
- 不把 `model_draft` 默认加入训练集；
- 不复用现有 2D polygon prediction schema。

### 9.4 验收标准

- Contract JSON 清楚列出 specimen、input volume、label volume、material map、training config、safety；
- `prepare_dataset` 至少能生成 dataset manifest 或调用 mock backend 完成；
- `train` 能登记 model manifest；
- `predict` 能读取 result JSON；
- prediction artifact 只导入 `model_draft`；
- 已有 `manual_truth` 未被覆盖；
- 每次运行都有 run_id、run_dir、日志和 provenance；
- 失败结果不会导入项目。

### 9.5 研究流程意义

通过本阶段后，Ant 3D Workbench 具备“人工标注 -> 训练 -> 自动粗标 -> 人工复核”的 TIF 体数据迭代闭环。

### 9.6 阶段复核问题

- 后端是否只能写指定 output_dir？
- result JSON 是否足够追溯模型来源？
- 预测 shape 是否和 working volume 匹配？
- 用户是否能清楚知道当前看到的是模型草稿而不是人工真值？

## 10. 阶段 6：主界面入口重排、PDF 下沉、旧项目兼容边界

### 10.1 目标

把产品入口调整为更符合 Ant 3D Workbench 的 STL/TIF 双项目体系，同时保留旧 2D/STL 工作流和 headless PDF 能力。

### 10.2 建议实现范围

核心能力：

- 新建项目时选择 STL/2D project 或 TIF Volume project；
- 打开项目时根据 `project_type` 或 schema 自动进入对应界面；
- 旧 TaxaMask JSON 继续进入 Labeling Workbench；
- TIF project 进入 TIF Volume Workbench；
- PDF Processing 从主标签隐藏或移到非主入口；
- 保留 `tools/agentic` 和 PDF 底层代码；
- UI 文案说明 PDF 现在更适合作为文献证据或 headless workflow。

### 10.3 不在本阶段做

- 不删除 PDF 底层代码；
- 不把 PDF skill 完整迁移到新插件；
- 不重写 STL 训练框架；
- 不做直接 3D mesh surface painting；
- 不把 STL 和 TIF 合成一个大 workspace。

### 10.4 验收标准

- 旧项目打开路径不破坏；
- TIF project 打开路径进入 TIF 工作台；
- 新建项目流程能明确区分项目类型；
- PDF 不再作为主视觉工作台标签干扰 STL/TIF 主流程；
- 现有测试中与旧工作台相关的关键测试仍通过；
- README 是否需要同步，由本阶段改动幅度决定。

### 10.5 研究流程意义

通过本阶段后，用户进入软件时能清楚选择自己是在做外部形态渲染图标注，还是在做内部结构体数据标注。

### 10.6 阶段复核问题

- 旧 TaxaMask 项目是否还能安全打开？
- TIF 和 STL 项目入口是否足够清楚？
- PDF 下沉是否只是界面重排，而不是丢失能力？
- 用户是否会误以为 TIF 使用旧 Locator/SAM 训练逻辑？

## 11. 阶段 7：总体验收、文档同步与最终汇报

### 11.1 目标

完成全链路验证，清理临时产物，同步必要文档，并给出面向研究流程的最终汇报。

### 11.2 建议实现范围

- 运行核心测试；
- 运行 TIF project 单元测试；
- 使用 mock 或真实 AMIRA 样例完成导入 smoke test；
- 使用 mock backend 完成 predict 导入 `model_draft` smoke test；
- 检查 `.tmp_validation/` 是否清理；
- 检查是否误加入数据库、模型权重、运行输出；
- 必要时同步 `LLM_CONTEXT_DETAILED.md`；
- 如果 public positioning 或安装依赖变化明显，更新 `README.md`；
- 如果用户要求，再更新 `CHANGELOG_zh.md`。

### 11.3 总体验收标准

- TIF project 可以创建、保存、打开；
- AMIRA 样例可以只读导入；
- slice viewer 可以显示 image 和 label overlay；
- brush edit 可以保存到 `working_edit`；
- 人工确认后可以更新 `manual_truth`；
- backend prediction 只能进入 `model_draft`；
- 旧 2D/STL 工作流可继续使用；
- PDF 底层工具未被删除；
- 数据安全边界符合设计文档。

### 11.4 最终汇报格式

最终汇报建议包含：

- 完成了哪些阶段；
- 每个阶段对研究流程的意义；
- 改动的主要文件；
- 新增数据结构和输出目录；
- 测试和验证结果；
- 仍然存在的风险；
- 建议下一轮优化方向。

## 12. 每阶段严格复核模板

每个大阶段完成后，建议使用固定模板：

```text
阶段名称：

一、程序现在能做什么
- ...

二、对研究流程意味着什么
- ...

三、改动的主要文件
- ...

四、数据写入位置
- ...

五、运行的验证
- ...

六、数据安全检查
- manual_truth 是否被保护：
- model_draft 是否保持草稿：
- 原始 AMIRA 文件是否只读：
- 临时验证产物是否清理：

七、发现的问题或剩余风险
- ...

八、是否建议进入下一阶段
- 建议 / 暂不建议
- 原因：
```

## 13. 需要用户额外提供或确认的材料

在正式开始超长任务前，最好补充或确认：

- 真实 AMIRA 样例目录路径；
- 样例文件中哪些是标准输入，哪些只是辅助脚本或派生产物；
- 已知 shape、material 数量和几个 material 名称；
- 是否允许新增 `zarr` / `ome-zarr` / `tifffile` / `numpy` 等依赖；
- 第一版 OME-Zarr metadata 严格程度；
- TIF 工作台 UI 的最低可接受操作流程；
- 是否接受阶段 1 先用 mock volume/label 测试，阶段 2 再接真实 AMIRA；
- 是否需要在每个阶段通过后本地 commit，还是只在更大里程碑时 commit。

## 14. 明确暂不进入第一轮的事项

第一轮超长实施不应默认包含：

- AMIRA `.labels` 写回；
- 直接 3D mesh 表面涂色；
- STL 到 TIF pseudo-label bridge；
- 完整 PDF skill 迁移；
- 内置 nnU-Net 或 MONAI 训练器；
- 云端训练；
- 多人协作版本冲突；
- 复杂 slice 级质量评分；
- 自动 route scoring；
- 自动把模型草稿升级为训练真值。

这些事项可以作为后续专项阶段，但不应混入第一轮核心闭环。

## 15. 开工条件

建议满足以下条件后再开始编码：

- 用户已阅读并确认本计划；
- 用户已确认阶段暂停复核方式；
- 用户已确认真实 AMIRA 样例路径或允许先用 mock 数据；
- 用户已确认依赖新增边界；
- 用户已确认本轮第一目标是 TIF project + AMIRA + slice viewer + edit + backend contract 闭环；
- 用户已确认“第一轮 TIF 核心闭环”和“后续完整需求覆盖阶段”的边界；
- 用户明确下令开始。

在用户下令前，本计划只作为执行准备，不代表已经开始改动核心程序。

## 16. 核对需求文档后的补充覆盖项

本节是对 `README.md`、`需求对齐_zh.md`、`TIF项目结构实施设计_zh.md`、`AMIRA导入适配实施设计_zh.md` 和 `TIF后端契约_v1_实施设计_zh.md` 逐项核对后的补充。

结论：

- 原计划对 TIF 项目结构、AMIRA 只读导入、slice viewer、人工编辑、TIF 后端契约和数据安全边界基本匹配；
- 原计划对 STL rendered-view 轻量迁移、普通 TIF stack 导入、导出/交换格式、PDF 文献证据层、跨项目 specimen 关联写得不够具体；
- 如果用户要求“完成所有需求文档中的方向”，这些补充项需要作为后续阶段进入执行计划。

### 16.1 普通完整 TIF stack 导入

需求来源：

- `需求对齐_zh.md` 明确第一阶段原始输入支持一个完整 TIF stack 文件；
- TIF Mode 不能只服务 AMIRA，也要能表示共聚焦、micro-CT 等不同切片 TIF 数据。

原计划遗漏点：

- 阶段 2 重点写了 AMIRA，只读导入很清楚；
- 但没有单独写普通 `.tif` / `.tiff` stack 导入或注册路径。

补充实施项：

- 支持从单个 multi-page TIF/TIFF 创建或导入 specimen；
- 生成 `working/image.ome.zarr/` 或第一版可恢复 sidecar；
- 记录 raw TIF source path、shape、dtype、spacing、modality、orientation；
- 没有 label 时生成空白 `working_edit`，但不自动生成 `manual_truth`；
- 用户可后续创建 material map 并开始人工标注。

验收补充：

- 一个没有 AMIRA 文件的完整 TIF stack 可以进入 TIF project；
- 空项目不会被误判为 train-ready；
- source/provenance 能说明它来自普通 TIF，而不是 AMIRA。

### 16.2 Material map 创建和编辑

需求来源：

- `需求对齐_zh.md` 说明新建 TIF 项目时允许用户建立内部结构 label 表；
- `TIF项目结构实施设计_zh.md` 要求 material map 至少保存 id、name、display color、trainable、source_name。

原计划遗漏点：

- 原计划强调 AMIRA material map 生成，但没有明确普通 TIF 项目的 material map 创建和编辑界面。

补充实施项：

- 新建 material；
- 编辑 display name、颜色、trainable；
- 保留 `0` 作为 background；
- 禁止随意重排已有 material ID，除非有显式迁移；
- UI 中能让用户区分“显示名称”和“训练 ID”。

验收补充：

- 普通 TIF 项目可以从空 material map 开始建立内部结构标签；
- 修改颜色不改变 label volume 中的整数 ID；
- train-ready 检查能识别没有 trainable material 的情况。

### 16.3 OME-Zarr / OME-NGFF metadata 严格程度

需求来源：

- 需求文档将 OME-Zarr / OME-NGFF 作为长期 sidecar 方向；
- 同时允许简单数组文件只作为临时实现产物。

原计划遗漏点：

- 原计划把依赖和 OME-Zarr 严格程度列为阶段 0 需要确认，但没有把它变成验收边界。

补充实施项：

- 阶段 0 必须确认第一版 sidecar 严格程度；
- 如果先用简化 Zarr sidecar，需要在 project metadata 里标明格式和后续迁移风险；
- 如果写 OME-NGFF metadata，需要至少记录 axes、shape、dtype、spacing、labels 角色。

验收补充：

- 项目打开逻辑不能只靠目录名猜格式；
- sidecar metadata 必须足以恢复 image/label shape 和角色；
- 后续升级到更完整 NGFF 时有迁移入口。

### 16.4 导出和交换格式适配

需求来源：

- `需求对齐_zh.md` 要求 OME-TIFF 用于显微图像交换；
- NIfTI / NRRD / MHA / 3D TIFF 用于模型和外部工具交换；
- `README.md` 提到 export volume labels for AMIRA/Avizo-style review and multiple model-training backends。

原计划遗漏点：

- 阶段 5 写了 contract 和 mock backend，但没有明确导出适配器。

补充实施项：

- 第一轮后端可以先生成 dataset manifest；
- 完整阶段需要实现至少一个训练导出适配器，优先根据用户后端选择决定；
- 推荐优先级：
  1. backend manifest + OME-Zarr 原样引用；
  2. NIfTI 或 NRRD，用于 nnU-Net/MONAI/3D Slicer 生态；
  3. OME-TIFF，用于显微图像交换；
  4. 其他格式按后端需要补充。

验收补充：

- 导出结果记录来源 specimen、label role、material map snapshot；
- 导出不修改项目内 `manual_truth`；
- 导出报告说明 spacing/orientation 是否完整。

### 16.5 Model record、metrics 和 modality adaptation

需求来源：

- TIF 后端设计要求每次训练和预测都有 model manifest、metrics、warnings、provenance；
- 需求文档强调共聚焦到 micro-CT 的 modality adaptation。

原计划遗漏点：

- 阶段 5 提到 model record，但没有明确按 material 指标、modality source/target 和 adaptation note。

补充实施项：

- model manifest 保存 backend、model family、训练 specimen、label role、material map snapshot；
- 保存 modality source/target 和 adaptation note；
- result JSON 允许 `metrics.summary` 和 `metrics.by_material`；
- UI 或报告至少能显示 warning 和失败原因。

验收补充：

- 用户能追溯某个预测来自哪个模型、哪批 specimen、哪个 material map；
- modality 信息不会被默认假设为 micro-CT；
- 共聚焦训练、micro-CT 预测的实验路径可以被记录。

### 16.6 STL rendered-view 项目轻量迁移

需求来源：

- STL Mode 第一阶段处理已经从 STL/mesh 渲染出来的多视角 2D 图片；
- 文件名包含 specimen 编号和固定视角名；
- 渲染图可能高达 64K；
- 现有 Labeling Workbench、Blink、Locator/SAM、route-appointed expert 尽量复用。

原计划遗漏点：

- 原计划阶段 6 只写了旧项目兼容和主界面入口，没有把 STL rendered-view 分组、固定视角、64K 高分辨率约束写清楚。

补充实施项：

- 设计 STL project 或 STL-derived 2D project 的轻量 schema；
- 按命名规则把 rendered views 自动分组到 specimen；
- 记录 fixed view name、source STL/mesh path、render provenance；
- 左侧栏从 image list 逐步过渡到 specimen-centered view；
- 保持训练按图片随机切分的现有策略；
- 不把 species/taxon identity 当作模型输入；
- 高分辨率图片需要保留现有可用路径，不在第一轮强行重写图像金字塔系统。

验收补充：

- 同一 specimen 的多个 view 能在 UI 中聚合；
- 旧 2D 项目仍可打开；
- STL label 类别仍独立于 TIF material map；
- 64K 图像处理策略不降低已有标注安全性。

### 16.7 Derived 2D / Review Mode

需求来源：

- `README.md` 把现有 2D annotation workbench 定位为 derived-image review and model-curation tools；
- 用途包括 rendered STL views、selected TIF slices 或 projection images。

原计划遗漏点：

- 原计划没有单独写 Derived 2D / Review Mode，只在旧工作台兼容里隐含保留。

补充实施项：

- 将现有 Labeling Workbench 明确命名或定位为 STL/Derived 2D Review；
- 允许后续从 TIF slice/projection 生成 review image，但不把它混入 TIF truth layer；
- 保留 Blink/local expert 作为 2D 派生图像复核工具。

验收补充：

- 用户不会误以为 derived 2D 标注等同于 TIF volume truth；
- TIF volume truth 仍以 label field 为准。

### 16.8 PDF 文献证据层和 skill 下沉

需求来源：

- PDF Processing 不再作为主界面核心模块；
- PDF 结果应作为文献证据、图像来源和 provenance；
- 后续迁移为 agent skill/headless workflow。

原计划遗漏点：

- 阶段 6 写了隐藏 PDF 主标签，但没有写轻量证据入口或 skill 迁移边界。

补充实施项：

- 第一轮只隐藏或降级主界面 PDF Processing，不删除代码；
- 后续设计 Literature Evidence 入口，用于查看 PDF、caption、page、candidate provenance；
- PDF skill 迁移作为单独专项，不混入 TIF 核心闭环；
- 保留 `tools/agentic` 批处理能力。

验收补充：

- PDF 底层工具仍可运行；
- 主界面不再让 PDF 看起来是 Ant 3D Workbench 的核心标注入口；
- 文献证据不会被误当作高质量 STL/TIF 训练主数据。

### 16.9 Cross-project specimen linkage 和 metadata_ref

需求来源：

- STL 和 TIF 是独立项目，但可以通过 shared specimen identifiers 或 import naming convention 轻量关联；
- specimen 编号不是物种名，物种信息通过 master metadata table 或 `metadata_ref` 解决。

原计划遗漏点：

- 阶段 1 提到 specimen 和 `metadata_ref`，但没有明确跨项目链接边界。

补充实施项：

- TIF 和 STL 项目各自保存 `specimen_id`；
- 可选保存 `metadata_ref`；
- 不在第一轮建立大型统一 workspace；
- 后续可做轻量 link resolver，用 specimen ID 对齐两个项目。

验收补充：

- TIF 项目不依赖 STL 项目才能打开；
- STL 项目不依赖 TIF 项目才能打开；
- shared specimen ID 只用于追溯和导航，不改变训练输入。

### 16.10 STL-to-volume pseudo-label bridge

需求来源：

- `README.md` 的初始 checklist 提到 STL surface labels 转 TIF pseudo-label volumes 和 QC report。

原计划遗漏点：

- 原计划把它放在“不进入第一轮”，但没有说明后续专项阶段。

补充判断：

- 这是高风险专项，不应进入 TIF 核心闭环；
- 需要先有稳定 STL specimen grouping、TIF specimen registry、坐标/尺度/配准假设；
- 必须有 QC report，否则很容易把表面标签错误投射到体数据。

后续专项验收方向：

- 明确 source STL view、target TIF volume、配准方式；
- 输出 pseudo-label role，不能默认成为 `manual_truth`；
- QC report 必须说明覆盖率、冲突、不可投射区域和人工复核需求。

### 16.11 更新后的完整阶段建议

如果目标是完成所有设计文档方向，而不是只完成第一轮 TIF 核心闭环，建议总阶段扩展为：

```text
阶段 0：实施前基线检查与依赖确认
阶段 1：TIF Project 数据层最小骨架
阶段 2：普通完整 TIF stack 导入和 material map 创建
阶段 3：AMIRA 只读导入最小闭环
阶段 4：TIF slice viewer 与 label overlay
阶段 5：TIF 画笔编辑、擦除、撤销重做与人工确认
阶段 6：TIF backend contract v1、训练导出适配和预测导入 model_draft
阶段 7：主界面入口重排、旧项目兼容、Derived 2D Review 定位
阶段 8：STL rendered-view project 轻量迁移和 specimen 分组
阶段 9：PDF 文献证据层下沉和 headless/skill 边界
阶段 10：总体验收、文档同步与最终汇报
```

其中阶段 1 到阶段 6 是 TIF 体数据闭环，阶段 8 和阶段 9 是完整产品方向的补齐。STL-to-volume pseudo-label bridge 建议作为阶段 11 或后续专项，不应在没有配准和 QC 设计时混入本轮主线。

## 17. 2026-05-16 补齐执行结果

本节记录在“轻量完成/未完全完成项”补齐后的实际落点，作为后续复核基线。

### 17.1 已落实到位

- **OME-Zarr / OME-NGFF metadata**  
  `AntSleap/core/tif_volume_io.py` 现在在 `.ome.zarr/` sidecar 内写出最小 OME-NGFF v0.4 / Zarr v2 元数据和未压缩 chunk，同时保留 `array.npy` 作为 AntSleap 内部快速恢复副本。metadata 标记 `ome_ngff_complete: true`，记录 axes、shape、dtype、spacing、role 和 chunk 信息。

- **TIF 导出和交换格式适配**  
  `AntSleap/core/tif_export.py` 已支持 OME-TIFF、普通 TIFF、NRRD、MHA、NIfTI 导出，并写出 `tif_training_export_manifest.json`。导出只读取 train-ready specimen 的 `manual_truth`，不修改项目内真值。

- **nnU-Net / MONAI 数据集布局**  
  已新增 `export_nnunet_dataset(...)` 和 `export_monai_dataset(...)`。它们生成 nnU-Net 风格 `imagesTr/labelsTr/dataset.json` 和 MONAI 风格 `monai_datalist.json` / manifest。真实训练仍由用户自己的后端环境执行，AntSleap 负责可追溯数据交接。

- **TIF backend prepare_dataset 导出闭环**  
  `TifBackendRunner.run_action("prepare_dataset")` 会先生成训练导出目录，再把 `dataset_manifest` 和 `dataset_formats` 写入 contract，供外部后端使用。

- **Material map 创建和编辑 UI**  
  TIF workbench 已支持新增、编辑、删除 material。`0` 号 background 被保护；如果某个 material ID 仍存在于 label volume 中，删除会被阻止，避免留下无法解释的标注整数。

- **STL rendered-view project 轻量迁移**  
  保留 `ant3d_stl_rendered_project_v1` / `stl_rendered_views` 轻量 registry 能力和 `StlRenderedProjectManager`，用于按文件名中的 specimen ID 和固定 view name 分组，保留 source/provenance。但它不再作为主界面的平级工作台出现，避免和真正负责标注的 2D Labeling Workbench / Blink 流程混淆。

- **STL rendered views 到 Derived 2D Review 的桥接**  
  新增 `AntSleap/core/stl_review_bridge.py`。`Import STL Rendered Views to Labeling Workbench` 可直接把 rendered views 注册到现有 2D Labeling Workbench，复用 Blink、Locator/SAM 和现有训练路径，同时在 image provenance 中记录 optional STL project、specimen、view 和来源路径。打开旧的 STL rendered-view registry JSON 时，也会登记进 Labeling Workbench，而不是切到独立 STL 标签页。

- **PDF 文献证据层轻量索引**  
  新增 `AntSleap/core/pdf_evidence.py`，保存 PDF evidence index：source PDF、page、caption、candidate path、specimen ID、metadata_ref 和 provenance。该索引只做证据/来源追溯，不进入 TIF `manual_truth`。

- **Cross-project specimen linkage**  
  新增 `AntSleap/core/specimen_linkage.py`，按 `metadata_ref` 或 normalized `specimen_id` 对独立 TIF/STL 项目生成 linkage 报告，不建立大 workspace，也不改变训练输入。

### 17.2 仍明确不进入本轮

- **AMIRA `.labels` 写回**：仍只读导入，不写回 AMIRA 原始标注。
- **直接 3D mesh painting**：STL 第一阶段仍处理 rendered 2D views，不直接在 mesh 表面涂色。
- **STL-to-volume pseudo-label bridge**：仍作为后续高风险专项，需要配准、覆盖率、冲突和 QC report 设计后再做。
- **内置 nnU-Net/MONAI 训练器**：本轮提供可追溯数据布局和后端契约，不在 AntSleap 内直接托管完整训练框架。

### 17.3 验收结果

使用 `antsleap` conda 环境完成：

```text
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest discover tests
Ran 193 tests in 5.201s
OK

C:\Users\admin\anaconda3\envs\antsleap\python.exe -m compileall -q AntSleap tests
OK
```

真实 AMIRA 样例目录仍可解析到 raw TIF、`.hx`、`.resampled`、`.labels`、`.MaterialStatistics` 和 `.surf`。
