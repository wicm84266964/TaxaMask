# unsloth-studio-finetune portable bundle

这个目录是给 **其他机器上的智能体** 直接接入使用的可迁移包。

这是 TaxaMask 维护的 Windows 扩展变体，版本为 `1.0.0-taxamask.windows1`。来源与同步策略记录在 `../EMBEDDED_SKILLS.json`，许可证见本目录 `LICENSE`。

## 包内文件

- `SKILL.md`：技能定义与运行边界
- `templates/qwen35_dual_gpu_windows_api.template.json`：长期可复用的 Qwen3.5 双卡模板
- `templates/qwen35_dual_gpu_windows_api.smoke.template.json`：新机器 1-step 验证模板

## 目录约定

这个 skill 目录以后统一按下面规则放文件，避免把运行垃圾落到 `skill` 根目录：

- `runs/`
  - 需要保留的 YAML / JSON 配置
- `logs/<date>/`
  - 原始 `.log` / `.err.log`
- `runtime/<date>/`
  - Studio 运行时目录，例如隔离 home、pid、sqlite
- `cache/<date>/`
  - 编译缓存和可重建缓存
- `tmp/<date>/`
  - 一次性探测、修复、中转和试验目录
- `references/`
  - OpenAPI、说明性导出文件

根目录只保留 skill 本体文件和这些子目录，**不要**把 `unsloth` 运行日志、`isolated_studio_home`、编译缓存或探测目录直接放在仓库的 `skills/` 根目录。

## 迁移前提

1. 目标机器已安装 Unsloth Studio
2. 目标机器是 Windows，并且有 2 张可见 NVIDIA GPU（如果要双卡）
3. 如果训练 Qwen3.5，Studio venv 中的 `transformers` 必须满足 `>= 5.2.0`
4. 本地数据必须是 **UTF-8 JSONL**，不能直接拿坏编码的原始文件训练
5. API key 和 Hugging Face/W&B token 只保存在本机运行环境，不写入模板、日志、Agent 对话或仓库

## 已验证的成功路径

- **Qwen3.5 Windows 双卡：Studio API + `gpu_ids=[0,1]` + `load_in_4bit=false`**
- **Qwen3.5 Windows 双卡 + 4bit：已验证失败，不应作为默认模板**

## 建议接入方式

1. 从仓库内的 `skills/unsloth-studio-finetune-portable` 读取 skill
2. 让智能体先探测目标机器上的：
   - `unsloth.exe`
   - Studio Python
   - GPU 可见性
3. 先用 `templates/qwen35_dual_gpu_windows_api.smoke.template.json` 跑 1-step 验证
4. 验证成功后，再切换到长期模板 `templates/qwen35_dual_gpu_windows_api.template.json`

## 说明

本包**不包含**：
- 本机的 `unsloth_compiled_cache`
- 本机训练输出
- 本机数据集文件
- 本机临时 smoke YAML

这些内容都不适合作为可迁移 skill 交付物。
