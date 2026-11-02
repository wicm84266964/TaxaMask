# 物种与个体工作台：智能体接口 v1

入口：`tools/agentic/instance_workbench.py`。Ask Agent 提供当前项目类型、项目 ID、图像 ID、实例数和本文引用，区别于旧 labels.parts/Blink 链路。

## 可调用动作

```text
python tools/agentic/instance_workbench.py capabilities
python tools/agentic/instance_workbench.py inspect --project <project.instance.json> --out <context.json>
python tools/agentic/instance_workbench.py validate --project <project.instance.json>
python tools/agentic/instance_workbench.py export --project <project.instance.json> --task detect --format coco --out <输出目录>
python tools/agentic/instance_workbench.py propose_instances --project <project.instance.json> --request <request.json>
python tools/agentic/instance_workbench.py train --project <project.instance.json> --task detect --weights <本地初始权重> --epochs 50 --batch 4 --imgsz 640 --device cpu
python tools/agentic/instance_workbench.py predict --project <project.instance.json> --image-id <image_id> --model-manifest <model_manifest.json> --out <proposals.json>
```

分类预测另传 `--instance-id`，只预测所选个体裁剪。训练和预测沿用实例项目设置中的内置/外部后端。预测只产生建议，不直接保存标注；训练只读取确认后的冻结快照，CLI 会等待训练完成并返回输出位置，日志位于本次运行目录。导出格式与 task 必须匹配，分类使用 `--format classification`。

正常结果为 JSON，失败为 status=failed 且进程退出码非零。inspect 可能包含本机来源路径，供本地智能体诊断，不应直接公开。

## 修改请求

CLI 以只读方式读取数据库，GUI 打开时也可 inspect/validate/export。标注修改通过队列由 GUI 的唯一写者执行，不允许第二个进程抢写数据库。

```json
{
  "schema_version": "taxamask-instance-agent-request-v1",
  "request_id": "proposal_batch_001",
  "project_id": "instance_project_example",
  "expected_revision": 12,
  "action": "propose_instances",
  "instances": [
    {"image_id": "image_example", "category_id": "category_a", "bbox_xyxy": [10, 20, 40, 60], "score": 0.9},
    {"image_id": "image_example", "category_id": "category_a", "bbox_xyxy": [60, 20, 90, 60], "score": 0.8}
  ]
}
```

request_id 为 1–100 位字母、数字、下划线或连字符；expected_revision 来自最新 inspect。一个请求最多 10000 个候选且不超过 16 MiB。可附加同尺寸 mask_rle；不得传 review、confirmed 或其他未声明字段。

请求文件进入 `<项目>/agent_requests/pending/`，GUI 在没有模型任务或正在绘制操作时处理，结果写入 `agent_requests/results/<request_id>.json`：

- queued：尚未处理。工作台未打开时会保持此状态，不代表已写入。
- applied_as_drafts：整个批次已事务提交，附带实例 ID 和新修订。
- rejected：项目/修订不符、原图改变、无效几何、未知类别或非法字段等。需要重新 inspect 后生成新请求。

同请求 ID 已应用后不会重复创建个体；任一对象验证失败，整个批次不写入。界面显示请求结果并刷新个体列表。人工确认、删除既有标注、改写模型配置和修改旧部位项目不属于此接口能力。智能体无法把自己的预测标为人工真值。

关闭 GUI 前要等待正在运行的任务，或先取消；队列文件不会因为窗口关闭自动执行。不要直接操作 SQLite 或调用旧 auto_annotate_project.py 来绕过实例协议。
