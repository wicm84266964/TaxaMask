# TaxaMask Ant-Code 原生接入与源码只读计划

日期：2026-05-20

## 背景

TaxaMask 需要把 Ant-Code 作为内嵌研究助手使用。它必须在 TaxaMask 源码仓库中启动，因为研究者遇到的问题通常同时涉及源码、配置、项目 JSON、TIF/STL/PDF 工作流文档和运行日志。如果把 Agent 放到另一个小工作区，它看不到真实项目结构，反而会降低排查质量。

同时，内嵌 Agent 不应直接修改 TaxaMask 源码。源码改动仍应由维护者在明确开发任务中完成；研究者日常使用时，Agent 可以帮助读源码、解释报错、调整配置、整理项目文件、检查数据路径和生成操作建议。

## 本次边界

- Ant-Code 在 TaxaMask 仓库根目录启动。
- Ant-Code 可以读取 TaxaMask 源码，以便解释错误和定位配置问题。
- Ant-Code 可以修改非源码文件，例如项目 JSON、配置 JSON、文档、运行计划、导出清单等。
- Ant-Code 不能修改 TaxaMask 源码文件。
- 启动页聊天区域保持现有大小，不扩张为占据半屏的控制台。
- 嵌入 WebUI 保留现有 Dashboard 能力，但视觉上更像 TaxaMask 内置面板。

## 源码只读保护设计

新增 TaxaMask 专用 blocking hook：`denyTaxaMaskSourceWrites`。

拦截对象：

- 内置文件写入工具：`write_file`、`edit_file`
- shell 工具：`powershell`、`bash`
- filesystem MCP 写入入口：`mcp_call`

默认保护的源码区域：

- `AntSleap/`
- `core/`
- `tools/`
- `tests/`
- `vendor/ant-code/src/`
- `vendor/ant-code/tests/`
- `vendor/ant-code/scripts/`

默认保护的源码扩展名：

- Python/JavaScript/TypeScript/CSS/HTML
- shell 和 Windows 脚本，例如 `.sh`、`.ps1`、`.bat`、`.cmd`

保留可写的常见研究文件：

- `AntSleap/config/*.json`
- 项目 JSON
- `docs/`
- 工作流规划文档
- 标注项目和导出清单

## 启动方式

TaxaMask Agent 面板优先使用仓库内的 `vendor/ant-code` 源码启动 Dashboard，而不是继续调用外部打包 exe。这样 TaxaMask 专用 hook 会跟随当前仓库代码生效。

为了避免 vendored 源码缺少 `node_modules` 时无法启动完整 CLI，本次添加一个轻量 Dashboard 启动入口，只导入 Dashboard server，不导入 TUI 依赖。

运行环境变量：

- `LAB_AGENT_PACKAGE_ROOT=<repo>/vendor/ant-code`
- `LAB_AGENT_CONFIG=<repo>/AntSleap/config/taxamask_ant_code.config.json`

## UI 融合原则

- 保持聊天区域现有面积。
- 隐藏 Ant-Code Dashboard 中对 TaxaMask 启动页重复的侧边栏和文件预览栏。
- 保留对话、审批、反问、队列和上下文压缩能力。
- 用紧凑顶栏说明当前是 TaxaMask 内嵌 Agent，并提示源码只读保护已启用。
- 不把项目控制台做成抢占交流窗口的大面板。

## 验证点

- 直接写 `AntSleap/main.py` 会被 hook 阻止。
- 编辑 `docs/*.md` 或配置 JSON 不会被源码守卫阻止。
- shell 中明显写源码的命令会被阻止。
- filesystem MCP 写源码会被阻止。
- TaxaMask Agent 面板启动命令指向 vendored Ant-Code 源码和 TaxaMask 专用配置。
- GUI smoke 测试仍能构建启动页并识别 Agent 面板。
