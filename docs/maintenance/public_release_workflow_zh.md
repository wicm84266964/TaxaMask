# TaxaMask 开发版与正式发布版工作流

## 目录职责

- `C:\saveproject\LBJ-workspace\Formica-Flow-Latest`：唯一日常开发目录。保留完整本地 Git 历史，但不配置 GitHub `origin`，不能直接推送线上。
- `C:\saveproject\LBJ-workspace\open-source\TaxaMask`：正式公开发布目录。只跟踪 GitHub `main`，不在这里进行日常功能开发。
- `C:\saveproject\LBJ-workspace\TaxaMask-preprint`：预印本代码分支归档，继续跟踪公开的 `preprint-submission`，用于在研究时间窗口发生变化时快速恢复预印本版本。
- `C:\savedata\TaxaMask-preprint`：预印本文稿、图片、来源材料和验证资料，不属于代码发布目录。
- `C:\savedata\TaxaMask-preprint-code-20260712.bundle`：预印本代码完整 Git 历史离线备份。

开发版是功能来源，正式版是公开发布闸门。两个目录不能各自独立开发，否则会形成两条难以核对的产品主线。

## 同步原则

同步工具为 `tools/release/sync_public_release.ps1`。

它采用以下边界：

- 只允许复制开发仓库中已经被 Git 跟踪的文件；未跟踪和被忽略的文件默认不进入正式版。
- 拒绝 `.lab-agent`、`TaxaMask_outputs`、私有文档、临时验证目录、数据库、模型权重、PDF、TIF、数组数据、私钥和常见真实 API Key 格式。
- 正式版必须位于 `main`、工作区必须干净，且 `origin` 必须是 `https://github.com/wicm84266964/TaxaMask.git`。
- 开发版必须位于 `main`、工作区必须干净，而且不能存在名为 `origin` 的远端。
- 默认只预览新增、修改和删除文件；只有显式传入 `-Apply` 才复制文件。
- 同步不会自动暂存、提交、打标签或推送。

Git 跟踪只是第一层允许清单，不代表文件天然可以公开。任何新数据格式、示例数据、模型或配置文件仍需人工判断是否应该进入公开源码。

## 日常开发

1. 只在 `Formica-Flow-Latest` 开发和测试。
2. 本地运行配置、API Key、项目数据库、PDF/TIF、模型权重和输出放在被忽略位置。
3. 完成一个可回退节点后，在开发版创建本地提交。
4. 发布前确保开发版位于 `main` 且 `git status --short` 无输出。

## 发布前预览

在开发版运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools\release\sync_public_release.ps1
```

检查输出中的 `ADD`、`MODIFY` 和 `DELETE`。任何意外数据、配置、临时文件或大文件都必须先在开发版解决，不能到正式版再临时隐藏。

## 应用同步

确认预览清单后运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools\release\sync_public_release.ps1 -Apply
```

然后进入正式版：

```powershell
cd C:\saveproject\LBJ-workspace\open-source\TaxaMask
git status --short
git diff --check
git diff --stat
git diff
```

## 正式版验证

验证必须在 `open-source\TaxaMask` 重新执行，不能只引用开发目录的测试结果。

基础发布检查：

```powershell
cd vendor\ant-code
npm ci
npm run verify:release
cd ..\..
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_agentic_contract tests.test_tif_agent_context
C:\Users\admin\anaconda3\envs\taxamask\python.exe -m unittest tests.test_config_cleanup tests.test_platform_open tests.test_poppler_discovery tests.test_runtime_device tests.test_generic_export_schema tests.test_window_geometry tests.test_path_identity tests.test_agent_context_routes tests.test_embedded_taxonomy_paper_finder tests.test_gui_smoke
```

同时运行本次改动直接相关的 GUI、TIF、2D、Blink、VLM、PDF 或导出测试。涉及共享架构、数据存储或跨项目任务时，应扩大到完整相关测试组。

测试后删除正式版中生成的依赖和临时产物，再确认：

```powershell
git status --short
git diff --check
```

## 提交与发布

1. 应用同步后，在正式版复核变更清单和敏感信息扫描结果。
2. 在正式版从 `main` 创建公开候选分支，不直接提交或推送 `main`。
3. 只在候选分支创建公开 commit，推送候选分支并创建 Pull Request。
4. 等待 Cross-platform smoke 的 Windows、Ubuntu、macOS 矩阵全部通过，再合并 Pull Request。
5. 合并后更新本地正式版 `main`，再次运行同步脚本预览；开发版与正式版应显示零文件差异。
6. 需要发布版本时，在 GitHub Actions 页面运行 `Create release`，选择 `main` 并填写新的版本号。
7. 发布工作流会复核 CI、创建不可变 tag 和 GitHub Release；不要手工创建、移动或覆盖公开 tag。
8. 发布后核对远端 `main`、tag、Release 和本地提交哈希一致。

如直连 GitHub 被重置，可仅对单次命令使用 `http://127.0.0.1:7897`，不要写入全局代理配置。

## 禁止事项

- 不在开发版配置 GitHub `origin` 或直接 push。
- 不直接推送正式版 `main`，也不绕过必需的 CI。
- 不在正式版开展未同步回开发版的功能开发。
- 不通过整目录复制、压缩包覆盖或资源管理器拖拽完成发布。
- 不在正式版提交 `.lab-agent`、本地配置、数据库、模型、研究数据或运行输出。
- 不因为同步脚本通过就跳过人工差异审阅和相关测试。
