# Final Handoff Prompt

Copy this into the next Codex conversation:

```text
我们继续 C:\saveproject\LBJ-workspace\lab-agent 里的 Ant Code clean-room TUI 重构。

请先完整阅读这个 handoff 文件夹：
C:\saveproject\LBJ-workspace\lab-agent\docs\handoff\2026-04-29-tui-continuation

重点文件阅读顺序：
1. README.md
2. CURRENT_STATE.md
3. ANT_CODE_LATEST_STATUS.md
4. PLAN_DOCUMENT_STATUS.md
5. OPEN_TASKS.md
6. TESTING_AND_LAUNCH.md
7. FILES_OF_INTEREST.md

背景和仓库关系：
- C:\saveproject\LBJ-workspace\ant-code-latest 是现有 Ant Code 项目，也是本次 clean-room 重构的主要产品/行为参照基线。
- C:\saveproject\LBJ-workspace\lab-agent 是新的 clean-room 实现仓库，也是当前唯一应该修改和测试的仓库。
- lab-agent 的功能、交互体验、用户预期以 ant-code-latest 的可观察行为、日志、审计结论、用户描述和净化后的规格文档为重要参考。
- 不要直接复制 ant-code-latest 的源码实现；不要把 ant-code-latest 当成当前实现仓库。

重要约束：
- 不要读取、复制或移植泄露 Claude Code 源码。
- 不要把本地网关 API key 写入仓库文件。
- lab-agent 工作区预期有大量未提交变更，这是前面连续重构阶段留下的正常状态；不要 reset、clean 或回滚不相关文件，除非用户明确要求。
- 如果 TUI 修复看起来没生效，优先确认是否真的从 lab-agent 启动，而不是跑到了全局 ant-code 或 ant-code-latest。

当前优先任务：
1. 验证并继续修复小窗口下鼠标滚轮/终端 scrollback 对完整历史会话的可达性。
2. 验证 /guide <message> 在长任务中的行为。当前实现是 abort 当前 turn，然后把引导提示插到队首运行，不是真正注入同一个 in-flight 模型请求。
3. 全面审计实际可用快捷键，确保 /keybindings 和 FooterBar 文案都与真实行为一致。
4. 继续提升 OpenCode-like 的 sky-blue TUI 体验，尤其是上下文长度显示、流式输出节奏、工具执行状态和小窗口布局。
5. 完成 live/manual 验证后，刷新验收、发布和计划状态文档。

启动命令：
cd C:\saveproject\LBJ-workspace\lab-agent
node .\src\cli\index.js tui

验证命令：
cd C:\saveproject\LBJ-workspace\lab-agent
npm run check

请先根据 handoff 文件给出你理解的当前状态和下一步计划，然后继续执行。
```
