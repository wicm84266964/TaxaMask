# Ant-Code 启动 JSON 错误排查与修复计划

## 1. 现象

点击 TaxaMask 启动页里的 Ant-Code 后，界面报告：

`Expected double-quoted property name in JSON at position 524262 (line 10674 column 3)`

这类错误通常表示某段 JSON 文本不是严格 JSON，例如属性名没有双引号、末尾多了逗号，或文件被截断。它不一定代表 Ant-Code 后端没有启动，也不一定代表当前标注项目已经损坏。

## 2. 已确认线索

- 打包版 `ant-code.exe dashboard --project ... --no-open` 可以启动，`/api/status`、`/api/sessions`、具体 session 接口均可返回合法 JSON。
- `.lab-agent` 下的会话和 skill 配置没有发现损坏 JSON。
- 仓库根目录存在一个确认损坏的旧备份：`test-head_broken_backup.json`。当前最近项目 `test-head.json` 本身可以被严格 JSON 解析。
- 这次修复不移动、不删除任何研究数据，也不修改 `lab-agent` 源码。

## 3. 修改目标

1. TaxaMask 启动 Ant-Code 前，轻量检查工作区根目录和当前上下文中明确指向的 JSON 项目文件。
2. 如果发现坏 JSON，在 TaxaMask 启动页中显示具体文件、行列和附近片段，让研究者知道需要隔离或修复哪份备份/项目文件。
3. Ant-Code 内嵌 WebView 使用独立的临时 profile，降低旧缓存、旧 sessionStorage 或旧页面状态影响新版本启动的概率。
4. 将 `Expected double-quoted property name...` 这类浏览器端 JSON 解析错误纳入 TaxaMask 状态栏提示。

## 4. 验证计划

- 使用 `antsleap` 环境编译相关 Python 文件。
- 运行 GUI smoke 中 Ant-Code 面板相关测试。
- 用同一环境启动 TaxaMask Agent 面板，确认 Ant-Code Dashboard 可以进入空闲界面。
