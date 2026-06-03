# Ant Code 使用说明

Ant Code 是一个本地运行的编码智能体。工具调用在本机执行，模型请求发往你配置的网关。

当前发布版本是 `3.0.0`。版本号按产品代际划分：`1.x` 对应早期源码参考和 clean-room 基线，`2.x` 对应自研架构、TUI、扩展和编排能力，`3.x` 对应当前 Dashboard/WebUI 发布线。详细沿革见 `docs\deployment\v3.0-dashboard-acceptance.md`。

## Windows 免源码版

对外分发请使用这个目录：

```powershell
dist\ant-code-windows-x64\
```

目录里包含：

- `ant-code.exe`：主程序。
- `configure-gateway.ps1`：一键配置网关、模型和 token。
- `config\`：配置模板和内置 skills。
- `docs\`：部署、审计、网关协议和安全边界文档。

这个目录不包含 `src\`、`tests\`、`node_modules\`、交接文件或计划文件。

## 一键配置模型和网关

在 `dist\ant-code-windows-x64\` 目录打开 PowerShell，运行：

```powershell
.\configure-gateway.ps1
```

如果 PowerShell 执行策略拦截，可以运行：

```bat
configure-gateway.cmd
```

按提示输入：

- 网关协议：大多数 OpenAI Chat Completions 兼容网关填 `openai-chat`。
- 网关 Chat URL：例如 `https://gateway.example.com/v1/chat/completions`。
- 健康检查 URL：可以留空。
- 网络模式：默认 `approved-web`，可以用 `web_search` 和已批准 host 的 `web_fetch`；严格内网模式填 `lab-only`。
- 模型名：例如 `mimo-v2.5`。
- 上下文 tokens 上限：不知道就先用默认值。
- 网关 token：输入时不会显示。

脚本会自动：

- 写入用户配置文件：`%USERPROFILE%\.ant-code\lab-agent.config.json`。
- 设置用户环境变量：`LAB_AGENT_CONFIG`。
- 设置用户环境变量：`LAB_MODEL_GATEWAY_API_KEY`。
- 把主智能体和子智能体都配置成同一个模型。
- 默认允许 `duckduckgo.com`、`github.com`、`raw.githubusercontent.com`、`api.github.com`、`r.jina.ai`，用于搜索和读取公开网页资料。
- 运行 `ant-code doctor` 检查配置。

配置完成后，重新打开一个终端再运行：

```powershell
.\ant-code.exe doctor
.\ant-code.exe gateway --live
.\ant-code.exe -p "Reply exactly: ready"
```

## 启动方式

默认命令仍然启动 TUI：

```powershell
ant-code
```

WebUI Dashboard 使用独立入口：

```powershell
ant-code dashboard
```

Dashboard 第一版只支持本机访问，默认地址是 `http://127.0.0.1:7410`，启动后会自动打开浏览器。端口被占用时会自动向后寻找可用端口。常用参数：

```powershell
ant-code dashboard --port 7410
ant-code dashboard --no-open
ant-code dashboard --project .
```

Dashboard 不提供局域网分享，不允许绑定 `0.0.0.0`。它复用和 TUI 相同的 `.lab-agent\sessions` 会话历史、核心智能体运行时和本地权限引擎。界面为深灰色三栏工作台：左侧任务线程，中间折叠活动流和最终回复，右侧图片、文本、Markdown、代码、PDF 和文件卡片预览。网页中也提供三层权限选择；需要确认的工具调用会在输入栏顶部弹出权限确认，需求核对会显示紧凑的可滚动选择面板。首次使用需要在网页中确认工作区信任；运行中发送新内容会进入队列，发送按钮会变成“运行中”并可点击中断，输入框有内容时可用“引导对话”把新要求交给当前任务，队列项内也可以对指定未开始任务执行“引导”。后台子智能体组会在输入栏上方以可折叠状态条显示；如果使用 `background=true` 和 `wakeParent=true`，Dashboard 会在子任务组完成后消费 wake prompt，父会话忙时排队、空闲时自动续跑，并在任务组记录中写入 `wakePromptConsumedAt`。清空上下文和压缩上下文都会先弹出确认。关闭 Dashboard 可以在网页左下角点击“关闭 Dashboard”并确认，也可以回到启动它的终端按 `Ctrl+C`。

Dashboard 底部会显示当前模型和文本/视觉/thinking 标签。点击模型区域的下拉按钮可以切换当前网关内已注册模型，也可以切换已保存的网关档案；打开本地模型配置入口后，可保存 URL、API key、模型 ID、显示名称、上下文窗口、主/子智能体模型和视觉子智能体。保存新 URL 或新 key 会创建/更新一个网关档案并设为当前活跃档案；同一网关不输入新 key 时会追加/更新该网关内模型。运行时仍只有一个网关档案生效，不会把 DeepSeek 和 MiMo 等不同网关混用。如果主模型是文本模型但当前网关内配置了视觉模型，图片任务会先由视觉子智能体生成视觉证据报告，再交给主模型继续处理。

## 临时命令行配置

如果不想交互输入，也可以直接传参数：

```powershell
.\configure-gateway.ps1 `
  -GatewayUrl "https://gateway.example.com/v1/chat/completions" `
  -Model "my-model" `
  -ApiKey "your-gateway-token" `
  -Protocol "openai-chat" `
  -NetworkMode "approved-web"
```

如果只是测试生成 JSON、不想写入用户环境变量，可以加 `-NoEnvWrite`。

如果你的环境必须禁止公网搜索和抓取，把网络模式设为：

```powershell
.\configure-gateway.ps1 -NetworkMode "lab-only"
```

## 以后切换模型或网关

再次运行：

```powershell
.\configure-gateway.ps1
```

或者手动编辑：

```text
%USERPROFILE%\.ant-code\lab-agent.config.json
```

通常只需要改：

- `modelAlias`
- `models[0].id`
- `models[0].label`
- `models[].modalities`：至少包含 `text`；视觉模型再包含 `image`
- `lab.gatewayUrl`
- `lab.gatewayHealthUrl`
- `lab.activeGatewayProfile` / `lab.gatewayProfiles[]`：Dashboard 保存的可切换网关档案；每次运行只使用当前活跃档案。
- `agents.modelTiers.cheap/default/strong/vision`
- `agents.vision.model`：同一网关下的视觉模型 ID

如果 token 变了，重新运行脚本最省事。

## 注意

`LAB_MODEL_GATEWAY_API_KEY` 是网关访问 token，不建议写进 JSON 文件。JSON 里只放模型名、网关 URL、上下文上限这类非密钥配置。
