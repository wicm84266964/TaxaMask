# TaxaMask 内置 Ant-Code 运行时

这个目录是 TaxaMask 随源码携带的 Ant-Code 运行时，用于本地智能体侧栏、Dashboard 和相关工具调用。

它不是本仓库的主产品入口。TaxaMask 把它作为内置组件保留下来，是为了让用户从源码运行时不必另外下载一份 Ant-Code。

## 保留内容

- `src/`：本地智能体运行时、Dashboard 服务、权限检查、会话存储和工具适配。
- `config/`：通用配置模板和内置技能。
- `scripts/`：语法检查、本地诊断、可选 Dashboard 资源重建等维护脚本。
- `package.json`、`package-lock.json`、`npm-shrinkwrap.json`：内置运行时的锁定依赖图。

历史计划、交接记录、上游发布材料和旧测试夹具不属于 TaxaMask 公开源码发布内容，已经从公开分支中移除。

## 配置方式

TaxaMask 使用 `AntSleap/config/taxamask_ant_code.config.json` 对接这份内置运行时。

模型网关凭据应放在本机用户配置或环境变量里，不要把真实 API key 或私有网关 token 提交进仓库。

常见环境变量包括：

- `LAB_AGENT_CONFIG`
- `LAB_MODEL_GATEWAY_PROTOCOL`
- `LAB_MODEL_GATEWAY_URL`
- `LAB_MODEL_GATEWAY_HEALTH_URL`
- `LAB_MODEL_GATEWAY_API_KEY`
- `LAB_AGENT_MODEL`

## 本地检查

在本目录运行：

```powershell
npm ci
npm run check:syntax
node .\src\cli\index.js doctor
```

面向 TaxaMask 用户的安装和研究流程说明，以仓库根目录的 README 和使用手册为准。
