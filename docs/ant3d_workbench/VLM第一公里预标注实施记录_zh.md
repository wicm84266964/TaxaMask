# VLM 第一公里预标注与 Blink 父级修复实施记录

日期：2026-05-26

状态：已完成第一轮代码落地，建议下一步用 10-20 张真实蚂蚁分类学图片做小样本复核。

补充复核记录：2026-05-26 晚间补做严格复核，发现并修复两处边界问题：供应商返回非 JSON 或空模型文本时，程序现在会保存原始响应和单图报告，避免只留下 `Expecting value` 这类难排查报错；删除某个部位标签时，会同步清理该部位的 `auto_box_meta`，避免旧 AI 草稿来源残留在项目 JSON 中。

## 1. 本次解决的问题

这次工作主要解决两个研究流程痛点。

第一，项目刚开始没有 Locator / Blink 素材时，研究者需要从零手工给 SAM 画提示框。现在可以让多模态大模型先根据网格图提出候选框，再由 SAM 生成草稿 polygon，帮助完成最麻烦的“第一公里”。

第二，Blink 合并进主工作台后，父级上下文解析过于积极。新建部位在只有一个主部位时会看起来自动挂到该父部位下。现在已改为显式确认：只有用户手动选择父级，或项目已有明确 route，才会形成父子关系。

## 2. 研究者实际怎么用

1. 在 `2D/STL Model Settings -> Training` 的 `AI Multimodal Pre-Annotation` 区域勾选要交给 VLM 预标注的部位。
2. 在 PDF Evidence Tools 中配置 Multimodal LLM API；缺少配置时，弹窗按钮会直接跳到 API 设置位置。
3. 回到主标注工作台，选择当前图像，点击顶部右侧工具流里的 `VLM Pre-Annotate`。
4. 程序生成网格图，调用多模态 API，解析候选框，并用候选框驱动 SAM 生成 `Auto-Annotated` 草稿。
5. 复核时，如果草稿正确，可以按空格确认当前部位，或点击 `Accept current image AI drafts` 一键通过当前图像已有 polygon 草稿。
6. 如果草稿错误，直接重新框选该部位并调用 SAM；人工结果会覆盖同部位 AI 草稿。

批量处理已导入所有图像前会二次确认，并且按图像线性执行。当前图像一键通过不会跨图像批量确认。

## 3. 数据安全边界

- VLM 结果只作为草稿框，不是训练真值。
- SAM 根据 VLM 框生成的 polygon 默认仍标记为 `Auto-Annotated`。
- 训练预检会跳过未复核的 `Auto-Annotated` 草稿。
- 只有空格确认、一键通过当前图像，或人工重新标注后的结果，才可以进入训练。
- 纯 `aibox` 且没有 polygon 的候选不会因为一键通过而变成训练材料。
- 运行产物保存在项目同级 `vlm_preannotation/`，该目录已加入 `.gitignore`，避免真实图像、raw response 和报告误入源码提交。

## 4. 主要源码位置

- `AntSleap/core/vlm_preannotation.py`：网格图、prompt、API 调用、JSON 解析和报告留档。
- `AntSleap/main.py`：GUI 入口、设置读取、批量队列、进度条、SAM 草稿写回、一键通过、设置跳转和 Blink 父级修复。
- `AntSleap/core/project.py`：VLM 设置、`auto_box_meta`、草稿确认状态和 AI 框清理。
- `AntSleap/core/training_preflight.py`：训练预检跳过未复核 `Auto-Annotated` 草稿。
- `tools/agentic/vlm_preannotate_project.py`：headless VLM 预标注入口。
- `tools/agentic/auto_annotate_project.py`：自动标注工具跳过未复核草稿。
- `AntSleap/ui/pdf_processing_widget.py`：多模态 API key 设置区保持可见，便于从 VLM 弹窗直接跳转。

## 5. 产物位置

真实运行时会生成：

- 网格图：`<project_dir>/vlm_preannotation/*_grid_*.png`
- 原始响应：`<project_dir>/vlm_preannotation/*_raw_response_*.txt`
- 单图报告：`<project_dir>/vlm_preannotation/*_vlm_preannotation_*.json`
- 批量汇总：`<project_dir>/vlm_preannotation/vlm_preannotation_summary_*.json`

这些是研究运行产物，不随源码提交。需要排查 API 或 JSON 解析问题时，优先查看 raw response 和 report。

## 6. 已验证内容

本轮已执行：

```text
python -m py_compile AntSleap/core/vlm_preannotation.py tools/agentic/vlm_preannotate_project.py tools/agentic/auto_annotate_project.py AntSleap/core/project.py AntSleap/core/training_preflight.py AntSleap/main.py
python -m pytest tests/test_vlm_preannotation.py tests/test_agentic_auto_annotate.py tests/test_training_preflight.py -q
python -m py_compile AntSleap/ui/pdf_processing_widget.py AntSleap/main.py
C:\Users\admin\anaconda3\envs\antsleap\python.exe -c "import AntSleap.main; print('main_import_ok')"
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_part_tree tests.test_locator_scope tests.test_ui_polish_scope
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_blink_bridge tests.test_ui_localization
```

说明：当前默认 Python 环境缺少 `torch`，`antsleap` 环境缺少 `pytest`，所以 GUI/Blink 相关测试使用 `unittest` 在 `antsleap` 环境中验证。

严格复核补丁追加验证：

```text
python -m pytest tests/test_vlm_preannotation.py -q
python -m py_compile AntSleap/core/vlm_preannotation.py AntSleap/core/project.py
```

## 7. 下一步小样本复核

建议先选 10-20 张真实蚂蚁分类学图版，人工记录：

- 哪些部位框可直接接受；
- 哪些部位需要轻微调整；
- 哪些部位经常错框；
- SAM polygon 是否稳定落在结构边界；
- VLM 是否会把比例尺、文字、局部插图或其他视图错当目标结构；
- 平均每张图节省多少手工框选时间。

如果常见部位框的可用率不高，应先调整目标部位列表、prompt 和网格密度，再考虑扩大批量处理。
