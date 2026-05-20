# Prompt For The Next Conversation

This was the earlier prompt draft. Prefer `FINAL_HANDOFF_PROMPT.md` for the
strict final handoff prompt.

Copy this into the next Codex conversation:

```text
我们继续 C:\saveproject\LBJ-workspace\lab-agent 里的 Ant Code clean-room TUI 重构。

请先阅读这个 handoff 文件夹：
C:\saveproject\LBJ-workspace\lab-agent\docs\handoff\2026-04-29-tui-continuation

其中 `PLAN_DOCUMENT_STATUS.md` 汇总了之前所有规划/规格文档的完成状态；
`plan-documents/docs/` 里保留了这些原始规划文档的副本。
`ANT_CODE_LATEST_STATUS.md` 写明了 ant-code-latest 是现有 Ant Code 项目，也是新仓库重构的主要产品/行为参照，同时说明不要混淆启动路径。

注意：lab-agent 工作区预期会有大量未提交变更，这是前面连续重构阶段留下的正常状态。不要 reset、clean 或回滚不相关文件，除非用户明确要求。

重点接续任务：
1. 验证并继续修复小窗口下鼠标滚轮/终端 scrollback 对完整历史会话的可达性。
2. 验证 /guide <message> 在长任务中的行为：当前实现是 abort 当前 turn，然后把引导提示插到队首运行。
3. 全面审计实际可用快捷键，确保 /keybindings 和 FooterBar 文案都与真实行为一致。
4. 继续提升 OpenCode-like 的 sky-blue TUI 体验，尤其是上下文长度显示、流式输出节奏、工具执行状态和小窗口布局。

请不要读取或复制泄露的 Claude Code 源码。我们只复刻可观察效果和清洁设计。
不要把本地网关 API key 写入仓库文件。
C:\saveproject\LBJ-workspace\ant-code-latest 是主要参照项目：新仓库 lab-agent 的功能、交互体验、用户预期都以它为重要参考。但当前实现和测试都应在 lab-agent 中进行；不要直接复制 ant-code-latest 的源码实现。

启动命令：
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui

验证命令：
npm run check
```
