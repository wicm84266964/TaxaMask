---
name: unsloth-studio-finetune
description: Operate local Unsloth Studio fine-tuning on Windows. Default to single-GPU CLI, and use the Studio API path for Qwen3.5 dual-GPU runs. On Windows, the proven dual-GPU default for Qwen3.5 is non-4bit via Studio API gpu_ids.
allowed-tools: powershell, read_file, list_files, glob
user-invocable: true
version: 1.0.0-taxamask.windows1
metadata: {"openclaw":{"os":["win32"],"requires":{"bins":["python"]}}}
---

# unsloth-studio-finetune

使用这个 skill 在 **Windows** 上操控本机的 **Unsloth Studio / CLI** 微调流程。

这个可迁移版本只保留可复用边界：**技能定义、长期训练模板、烟雾测试模板、迁移说明**。它不包含本机缓存、编译产物、训练输出或本机数据文件。

## 可迁移边界

- 不要假设固定的 `unsloth.exe`、Studio Python 或 site-packages 路径。
- 在目标机器上，智能体应先探测本机 Unsloth Studio 安装位置，再执行训练。
- 所有本地数据路径和输出路径都必须由用户或智能体在目标机器上显式提供。

## Ant Code local root

This skill is registered from:

```text
skills/unsloth-studio-finetune-portable
```

Ant Code may start from an arbitrary project cwd. Treat the path above as relative to the TaxaMask repository root. Use this skill root for reusable templates and references, but do not commit Unsloth runtime files unless they are intentionally reusable examples.

## 目录规范

此 skill 目录下的文件必须按“长期文件”和“运行产物”分层放置，**禁止**把 Unsloth 运行日志、临时目录、缓存目录直接写到 Ant Code 当前启动项目根目录，也不要写到仓库的 `skills/` 父目录。

### 根目录只允许保留

- `SKILL.md`
- `README.md`
- `templates/`
- `runs/`
- `logs/`
- `runtime/`
- `cache/`
- `tmp/`
- `references/`
- 迁移交接文档，例如 `WINDOWS_TRAINING_HANDOFF_*.md`

### 各目录用途

- `templates/`
  - 长期复用模板
  - 不放本机一次性试验日志
- `runs/`
  - 需要保留的 YAML / JSON 配置
  - 只保留值得复用或需要交接的配置
- `logs/<date>/`
  - 原始 `.log` / `.err.log`
  - 例如 `logs/windows-20260420/`
- `runtime/<date>/`
  - Studio 运行时目录
  - 例如隔离 home、pid、sqlite、临时 server 状态
- `cache/<date>/`
  - 编译缓存、patch 后缓存、可重建缓存
- `tmp/<date>/`
  - 探测目录、下载中转目录、修复中间目录、一次性实验目录
- `references/`
  - OpenAPI、接口描述、说明性导出文件

### 落盘规则

1. 所有命令日志必须写到 `logs/<date>/`，不能写到 workspace 根目录。
2. 隔离运行目录必须写到 `runtime/<date>/`，不能直接创建 `isolated_studio_home` 在根目录。
3. 编译缓存必须写到 `cache/<date>/`。
4. 一次性探测、下载修复、试验性中间目录必须写到 `tmp/<date>/`。
5. 新建配置时：
   - 需要长期保留的，放 `runs/`
   - 只用于一次性验证的，优先放 `tmp/<date>/`，确认有复用价值后再提升到 `runs/`
6. 训练输出模型、TensorBoard、数据集缓存不属于 skill 目录，必须继续写到用户指定的外部路径。
7. 结束一次实验后，应把根目录中误落的 Unsloth 相关文件回收进上述子目录，保持根目录整洁。

## 已验证的 Windows 事实

1. **CLI 单卡路径可用**，适合作为默认安全路径。
2. **CLI 不支持直接传 GPU flags**，不能用 `unsloth train --gpu-ids ...` 假装双卡。
3. **Qwen3.5 需要 `transformers >= 5.2.0`**，低版本会在模型加载前直接失败。
4. **Qwen3.5 双卡在 Windows 上的已验证成功路径是：**
   - 走 Studio API `POST /api/train/start`
   - 显式传 `gpu_ids = [0, 1]`
   - `load_in_4bit = false`
5. **Qwen3.5 双卡 + 4bit 在 Windows 上已验证失败**，错误是量化模型不能跨设备训练。
6. **本地数据集必须是 UTF-8 JSONL**。如果源文件不是 UTF-8，或行内存在坏字节/包装 JSON，先清洗再训练。

## 模式选择

### 模式 A：`single-gpu-cli`（默认）

适用场景：
- 用户没有明确要求双卡
- 只想先做保守验证
- 模型较小，单卡就够
- Studio server 不可用

原则：
- 用 YAML + `unsloth.exe train -c <config>`
- 先 `--dry-run`
- 这是稳定默认路径

### 模式 B：`dual-gpu-studio-api`（Qwen3.5 Windows 高级模式）

适用场景：
- 用户明确要求双卡
- 目标模型是 Qwen3.5 系列
- 愿意使用 Studio API 路线而不是 CLI 路线

原则：
- 必须通过 Studio API 提交
- 必须显式传 `gpu_ids = [0, 1]`
- **Windows 下默认使用 `load_in_4bit = false`**
- 如果用户要求 4bit 双卡，应先明确告知：当前已验证失败，需要重新做目标机复核，不能默认启用

## 训练前硬性检查

每次至少确认：
1. 目标机器已安装 Unsloth Studio
2. 目标机器 Studio venv 的 `transformers >= 5.2.0`（Qwen3.5 必需）
3. `nvidia-smi` 能看到 2 张 GPU
4. 数据集路径存在，且是 UTF-8 JSONL
5. 输出目录父目录可写
6. 双卡模式下，Studio health 可达：`GET /api/health`
7. 双卡模式下，API key 可创建

## 凭证与模型安全

- API key、Hugging Face token 和 W&B token 只能保存在本机运行环境或被 Git 忽略的本地配置中。
- 不要把 token 写进训练模板、Skill、命令日志、Agent 对话或仓库文件。
- `trust_remote_code` 默认保持 `false`；只有确认模型仓库及其自定义代码可信后才能启用。
- 训练数据、模型权重、检查点和 TensorBoard 输出必须写到用户指定的仓库外目录。

## 推荐工作流

### 单卡 CLI
1. 发现本机 `unsloth.exe`
2. 按目录规范创建本次实验的 `logs/<date>/`、必要时的 `runtime/<date>/` 或 `tmp/<date>/`
3. 生成 YAML
4. 跑 `--dry-run`
5. 通过后正式训练
6. 检查输出目录中的 `adapter_config.json`、`adapter_model.safetensors`、`checkpoint-*`

### Qwen3.5 双卡 Studio API
1. 启动 Studio server
2. `GET /api/health`
3. 创建 API key
4. 读取并填充 `templates/qwen35_dual_gpu_windows_api.template.json`
5. `POST /api/train/start`
6. 轮询 `/api/train/status` 与 `/api/train/metrics`
7. 完成后读取 `/api/train/runs` 或 `/api/train/runs/{run_id}` 获取最终 output_dir

## 双卡成功判定

满足以下条件时，才算双卡路径真正成功：
- `/api/train/start` 返回 `queued`
- `/api/train/status` 最终进入 `completed`
- `final_step > 0`
- `final_loss` 存在
- 训练输出目录存在，并且至少包含：
  - `adapter_config.json`
  - `adapter_model.safetensors`
  - `checkpoint-*` 或等价产物
- 运行中曾观察到两张 GPU 都分配到显存，且任务未因量化跨设备错误失败

## 双卡失败映射

### 1. 版本门槛错误
症状：Qwen3.5 提示需要 `transformers >= 5.2.0`
处理：先升级 Studio venv 的 transformers，再重试。

### 2. 4bit 双卡跨设备错误
症状：`You can't train a model that has been loaded in 8-bit or 4-bit precision on a different device...`
处理：保持 `gpu_ids=[0,1]`，但把 `load_in_4bit` 改成 `false`，走非量化双卡路径。

### 3. 数据编码错误
症状：数据加载或格式化时出现 `gbk` / `utf-8` / JSON 解码错误
处理：先把源数据清洗成标准 UTF-8 JSONL，再训练。

### 4. CLI 看见 2 张卡但训练仍只用 1 张卡
处理：这不算双卡成功，切回 Studio API 路线。

## 模板文件

- `templates/qwen35_dual_gpu_windows_api.template.json`
  - 长期可复用的 Qwen3.5 双卡训练模板
  - 默认是 Windows 上已验证成功的 **非4bit双卡路径**
- `templates/qwen35_dual_gpu_windows_api.smoke.template.json`
  - 1-step 烟雾测试模板
  - 用于新机器首次验证环境是否可跑通

## 输出时必须告诉用户

至少汇报：
- 实际采用的模式（单卡 CLI / 双卡 Studio API）
- 是否用了 `gpu_ids=[0,1]`
- 是否用了 `load_in_4bit=false`
- `phase` / `final_step` / `final_loss`
- 最终 `output_dir`
- 是否生成 `adapter_config.json` 和 `adapter_model.safetensors`
- 如果失败，明确是哪一类失败，而不是模糊说“训练没成功”

## 收尾要求

- 如果运行中产生了日志、缓存、运行时目录，必须在结束时确认它们位于 `logs/`、`cache/`、`runtime/`、`tmp/` 这些 skill 内部子目录。
- 如果发现 Unsloth 相关文件被误写到 Ant Code 当前启动项目根目录或仓库的 `skills/` 父目录，应在交付前整理回 skill 自己的子目录。
- 不要把“skill 本体文件”和“本机运行垃圾”混在一起交给下一位接手者。
