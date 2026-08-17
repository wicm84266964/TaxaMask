# Agent 交互与工作台布局优化设计稿

- 文档状态：已实施，开发版人工验收通过，随 v2.4.6 发布
- 版本：v1.0
- 日期：2026-08-16
- 范围：启动中心 / 内嵌 Agent 面板、2D/STL 标注工作台、TIF 体数据工作台的交互与布局优化
- 说明：本文只描述交互和布局改动，不包含安全加固内容。所有界面名称以中文界面实际显示为准。

---

## 1. 目标

1. 让 Ant-Code 的启动、停止、浏览器模式、失败恢复流程清楚可控。
2. 让 2D/STL 标注工作台右侧信息架构更清晰，运行状态和日志首屏可见。
3. 修正现有快捷键、工具栏溢出、翻译缺口等交互问题。
4. 统一中文文案，减少中英混排。
5. 不改变现有业务流程和数据处理逻辑，只调整 UI 结构、状态反馈和文案。

---

## 2. 改动总览

| 编号 | 位置 | 优先级 | 改动摘要 |
|---|---|---|---|
| D01 | 启动中心顶部右侧 | P0 | “启动 Ant-Code / 停止 Ant-Code”按钮状态联动 |
| D02 | 启动中心 Agent 区域 | P0 | 修复浏览器模式停止后重启不自动打开浏览器 |
| D03 | 启动中心 Agent fallback 页 | P1 | 增加“浏览器打开”按钮，URL 可选中复制 |
| D04 | 启动中心 Agent fallback 页 | P2 | 增加“重新加载”手动恢复入口 |
| D05 | 启动中心 Agent fallback 页 | P2 | Agent 上下文复制体验优化，增加“再次复制”按钮 |
| D06 | 启动中心 Agent fallback 页 | P3 | fallback 内容可滚动，补齐中文翻译 |
| D07 | 标注工作台右侧检查器 | P1 | 右侧改为“当前图片 / 自动标注 / 运行与日志”三个标签页 |
| D08 | 标注工作台顶部工具栏 | P2 | 低频操作收进“更多操作”菜单，避免窄窗口溢出 |
| D09 | 标注工作台右侧“当前图片”页 | P3 | “当前图片物种”上移，信息顺序调整 |
| D10 | 标注工作台右侧“当前图片”页 | P3 | “结构标签”树高度可伸缩，减少嵌套滚动 |
| D11 | 标注工作台快捷键 | P1 | Ctrl+S 修正；验证图片改为 Ctrl+Enter 并加入菜单 |
| D12 | 标注工作台顶部工具栏 | P3 | 移除隐藏的“打开子部位专家会话”死按钮 |
| D13 | 标注工作台工具条 | P3 | 为“手动绘制 / 魔棒 (SAM)”补充悬停提示 |
| D14 | TIF 工作台右侧 | P2 | “数据导入”置于首个标签页“导入与预览”顶部；“网格导出”移入“结果对比”页 |
| D15 | TIF 工作台顶部栏 | P2 | 增加运行状态精简显示，切换标签也能看到任务进度 |
| D16 | 全局中文文案 | P2 | 补齐翻译，统一中英混排和空格 |
| D17 | 启动配置目录 | P1 | 沙箱/WSL 下 `~/.config` 不可写时，自动回退到 `TaxaMask_outputs/config` |
| D18 | WSL 中文字体 | P1 | 无 CJK 字体时自动挂接 Windows 微软雅黑/宋体，修复中文显示异常 |
| D19 | TIF 后端 Python 探测 | P1 | 自动探测 Python 时跳过无权限目录，修复进入 TIF 工作台报错 |
| D20 | 内嵌模式加载过渡 | P2 | fallback 保持到 Dashboard 加载完成后再切换，减少黑色首帧闪烁 |

---

## 3. 详细改动项

### D01：“启动 Ant-Code / 停止 Ant-Code”按钮状态联动

**位置：** 启动中心 → 顶部右侧

**现状：**
- “停止 Ant-Code”在未运行时仍可点击。
- “启动 Ant-Code”在启动中、运行中仍可点击，重复点击会触发重置或重复加载。
- 用户只能依赖右侧小字“Agent 状态：...”判断当前状态。

**目标状态机：**

| 状态 | 启动按钮 | 停止按钮 | 启动按钮文案 |
|---|---|---|---|
| 未运行 | 可用 | 禁用 | 启动 Ant-Code |
| 启动中 | 禁用 | 可用 | 启动中... |
| 运行中 | 可用 | 可用 | 重新加载 |
| 停止中 | 禁用 | 禁用 | 停止中... |
| 失败 | 可用 | 禁用 | 启动 Ant-Code |

**实现方式：**
1. 在 `TaxaMaskAgentPanel` 中增加运行状态信号，例如 `running_state_changed(str)`，状态值使用 `stopped / starting / running / stopping / error`。
2. 在以下时机发出状态：
   - `start_dashboard()` 开始前：`starting`
   - Dashboard 健康检查通过：`running`
   - 启动失败 / 进程退出 / 健康检查超时：`error`
   - `stop_dashboard()` 开始：`stopping`
   - `stop_dashboard()` 结束：`stopped`
3. `MainWindowStartCenterMixin` 连接该信号，更新两个按钮的 `setEnabled()` 和文案。
4. 文案使用 `tr()`，新增翻译：
   - `Reload Ant-Code` → `重新加载 Ant-Code`
   - `Starting Ant-Code...` → `正在启动 Ant-Code...`
   - `Stopping Ant-Code...` → `正在停止 Ant-Code...`

**影响文件：**
- `AntSleap/ui/taxamask_agent_panel.py`
- `AntSleap/ui/main_window_start_center.py`
- `AntSleap/ui/main_window_i18n.py`

**验收标准：**
- 未运行时“停止”置灰。
- 点击“启动”后按钮立即进入启动中状态，且不能重复点击。
- Dashboard 就绪后“启动”文案变为“重新加载”，点击后仅刷新页面，不重复启动进程。
- 进程异常退出时按钮回到“启动 Ant-Code”可用状态。

---

### D02：修复浏览器模式停止后重启不自动打开浏览器

**位置：** 启动中心 → Agent 主区域；浏览器模式。

**现状：**
- `TaxaMaskAgentPanel._browser_opened_for_url` 用于防止重复打开浏览器。
- `stop_dashboard()` 清理了 `dashboard_url`，但未清理该标记。
- 停止后重启若再次分配到相同端口，浏览器不会自动弹出。

**实现方式：**
1. 在 `stop_dashboard()` 中重置 `self._browser_opened_for_url = ""`。
2. 在 `start_dashboard()` 分配新 URL 后同样重置一次，作为双保险。

**影响文件：**
- `AntSleap/ui/taxamask_agent_panel.py`

**验收标准：**
- Linux/WSL 浏览器模式下，执行“停止 Ant-Code”后再点“启动 Ant-Code”，浏览器能再次自动打开。
- 同一进程运行期间重复触发打开逻辑时，浏览器仍只打开一次。

---

### D03：fallback 页增加“浏览器打开”按钮，URL 可复制

**位置：** 启动中心 → 左侧 Agent 区域 → fallback 页（浏览器模式或内嵌加载失败时显示）。

**现状：**
- fallback 页只显示普通文字 URL。
- URL 不可选中、不可点击。
- 已有翻译“Open in browser → 浏览器打开”，但没有对应按钮。

**实现方式：**
1. 在 fallback 布局中增加按钮 `btn_open_dashboard_in_browser`，文案使用 `at("Open in browser", self.lang)`。
2. 点击后调用 `open_dashboard_in_browser(start_if_needed=True)`。
3. 按钮可见条件：`self.browser_mode` 或 `self.web_view is None`，且 `dashboard_url` 非空。
4. 将 fallback 中的 URL 放入独立 `QLabel`，设置 `setTextInteractionFlags(Qt.TextSelectableByMouse)`，允许用户手动选择复制。
5. 所有 fallback 显示更新集中在 `_update_fallback()` 中完成。

**影响文件：**
- `AntSleap/ui/taxamask_agent_panel.py`

**验收标准：**
- 浏览器模式下 fallback 页显示“浏览器打开”按钮。
- 点击按钮能打开或重新打开浏览器。
- URL 可以用鼠标选中复制。
- 内嵌模式正常运行时按钮隐藏，不遮挡 Dashboard 页面。

---

### D04：fallback 页增加“重新加载”手动恢复入口

**位置：** 启动中心 → 左侧 Agent 区域 → fallback 页。

**现状：**
- 内嵌页面加载失败或初始化失败后只能等待自动重试。
- 没有用户可以点击的恢复按钮。

**实现方式：**
1. 增加按钮 `btn_reload_dashboard`，文案：
   - 中文：`重新加载`
   - 英文：`Reload`
2. 点击逻辑：
   - 如果进程仍在运行且有 `dashboard_url`：调用 `_prepare_dashboard_load(reset=True)`。
   - 如果进程已退出：直接调用 `start_dashboard()`。
3. 按钮在存在 `_embedded_page_error` 或 `_preflight_error` 时显示。

**影响文件：**
- `AntSleap/ui/taxamask_agent_panel.py`

**验收标准：**
- 内嵌页面失败时能看到“重新加载”。
- 点击后重新走 preflight 和页面加载流程。
- 进程已退出时点击能重新拉起进程。

---

### D05：Agent 上下文复制体验优化

**位置：** 启动中心 → Agent 主区域；浏览器模式。

**现状：**
- 从工作台点击“询问 Agent”后，浏览器模式会自动把整段上下文写入系统剪贴板。
- 界面没有“再次复制”入口，用户误关提示后无法找回上下文。

**实现方式：**
1. `TaxaMaskAgentPanel` 保存最近一次上下文 `_last_context_prompt`。
2. 增加 `copy_agent_context_again()` 方法，重新写入剪贴板并更新状态文案。
3. fallback 页增加按钮 `btn_copy_agent_context_again`，文案：
   - 中文：`再次复制 Agent 上下文`
   - 英文：`Copy Agent context again`
4. 按钮可见条件：浏览器模式且 `_last_context_prompt` 非空。
5. 保留现有的自动复制行为，不改变当前操作流程。

**影响文件：**
- `AntSleap/ui/taxamask_agent_panel.py`

**验收标准：**
- 浏览器模式下点击“询问 Agent”后，fallback 页出现“再次复制 Agent 上下文”。
- 点击后剪贴板内容与首次复制的上下文一致。
- 切换语言后按钮文案正确。

---

### D06：fallback 页滚动与中文翻译补齐

**位置：** 启动中心 → 左侧 Agent 区域 → fallback 页。

**现状：**
- fallback 页没有滚动区域，URL、JSON 提醒、preflight error、page error 同时出现时会挤压布局。
- “Browser mode is active for this Linux/macOS/WSL session...”为硬编码英文。

**实现方式：**
1. 将 fallback 详情文字放入 `QScrollArea`，设置：
   - `setWidgetResizable(True)`
   - 垂直滚动条按需显示
   - 无边框
2. 详情文字仍使用现有 `fallback_detail` QLabel，保留换行和 `setWordWrap(True)`。
3. 将浏览器模式提示改为 `at("Browser mode is active...", self.lang)`，新增翻译：
   - `Browser mode is active for this Linux/macOS/WSL session. If the dashboard did not open automatically, open the URL below.`
   - → `当前为浏览器模式。如果浏览器没有自动打开，请打开下面的网址。`

**影响文件：**
- `AntSleap/ui/taxamask_agent_panel.py`

**验收标准：**
- 中文界面下不再出现该段英文。
- 长错误内容可以滚动查看，不挤压 Logo 和 URL。

---

### D07：标注工作台右侧改为标签页

**位置：** 标注工作台 → 右侧检查器。

**现状：**
- 右侧是一个长滚动区，依次包含：当前图片信息、自动标注、子部位标注、训练进度、日志。
- 在 768–920px 高度屏幕上，“训练进度”和“日志”通常不可见。

**目标结构：**

| 新标签 | 内容 |
|---|---|
| 当前图片 | 当前图片物种、结构标签、形态测量、文献性状、描述框 |
| 自动标注 | 父部位标注、子部位标注（Blink）相关控件 |
| 运行与日志 | 训练进度、训练结果、日志 |

**实现方式：**
1. 在 `_build_main_window_views()` 中创建 `self.workbench_inspector_tabs = QTabWidget()`，替换原 `workbench_inspector_scroll` 作为右侧面板容器。
2. 三个页面内部各自使用一个 `QScrollArea`，避免窗口较小时内容不可达。
3. 保持所有现有控件 attribute 名称不变，只改变父容器和布局：
   - `metadata_panel` → “当前图片”页。
   - `ai_panel` → “自动标注”页，但把 `training_progress_panel` 从 `ai_layout` 移除。
   - `training_progress_panel + logs_panel` → “运行与日志”页。
4. 新增标签文案翻译：
   - `Current Image` → `当前图片`
   - `Auto Annotation` → `自动标注`
   - `Run & Logs` → `运行与日志`
5. `MainWindowLiteratureBridgeMixin` 中原来的 `ensureWidgetVisible(desc_box)` 改为：切换到“当前图片”标签并确保 `desc_box` 可见。
6. 更新 `tests/test_ui_polish_scope.py` 中依赖旧布局顺序的断言。

**影响文件：**
- `AntSleap/ui/main_window_shell.py`
- `AntSleap/ui/main_window_literature_bridge.py`
- `AntSleap/ui/main_window_i18n.py`
- `tests/test_ui_polish_scope.py`

**验收标准：**
- 打开标注工作台，右侧显示“当前图片 / 自动标注 / 运行与日志”三个标签。
- 训练启动后，“运行与日志”标签中进度条和日志可见。
- “自动标注”标签中不再显示训练进度，避免信息重复。
- 文献性状功能仍能自动定位到描述框。

---

### D08：顶部工具栏低频操作收进“更多操作”

**位置：** 标注工作台 → 顶部工具栏。

**现状：**
- 左侧：导出数据集、导入并裁剪、批量切分拼图。
- 右侧：启动中心、VLM预标注、VLM批量预标、询问 Agent。
- 窄窗口下没有溢出策略，按钮可能被压缩或裁切。

**目标布局：**
- 左侧常驻：`导出数据集`
- 右侧常驻：`启动中心`、`VLM预标注`、`询问 Agent`
- “更多操作”菜单：`导入并裁剪`、`批量切分拼图`、`VLM批量预标`

**实现方式：**
1. 增加 `QToolButton`，文案 `更多操作` / `More Actions`，使用 `InstantPopup`。
2. 将“导入并裁剪 / 批量切分拼图 / VLM批量预标”按钮从布局中隐藏，但保留 widget attribute 和 `clicked` 连接。
3. 菜单动作在每次展开前同步：
   - 动作文案与按钮当前文案一致。
   - 动作 `enabled` 状态与对应按钮 `setEnabled()` 状态一致。
   - 点击动作时触发原按钮的 `click()`。
4. 现有 enable/disable 逻辑无需改动，继续操作原按钮对象。
5. 保留按钮的父容器，降低测试兼容性影响；新增测试断言“更多操作”菜单项状态与按钮一致。

**影响文件：**
- `AntSleap/ui/main_window_shell.py`
- `AntSleap/ui/main_window_presentation.py`
- `AntSleap/ui/main_window_i18n.py`

**验收标准：**
- 工具栏默认只显示高频按钮，窗口变窄时不再挤压。
- “更多操作”菜单显示三个低频操作，且中文文案正确。
- 当某个低频按钮被业务逻辑禁用时，菜单项同步禁用。
- 点击菜单项行为与原按钮一致。

---

### D09：“当前图片物种”位置上移

**位置：** 标注工作台 → 右侧“当前图片”标签页。

**现状：**
- “当前图片物种”出现在“结构标签”、增删按钮和形态测量之后，层级不直观。

**目标顺序：**

1. 当前图片物种
2. 结构标签
3. 结构树和增删按钮
4. 形态测量
5. 文献性状 / 描述

**实现方式：**
1. 调整 `metadata_layout` 的创建和添加顺序：
   - 先创建并添加 `image_taxon_panel`。
   - 再添加 `label_structures`、`part_list`、结构操作按钮。
   - 最后是 `group_morpho`、文献性状和描述框。
2. 更新 `tests/test_ui_polish_scope.py` 中关于 `part_list` 与 `image_taxon_panel` 顺序的断言。

**影响文件：**
- `AntSleap/ui/main_window_shell.py`
- `tests/test_ui_polish_scope.py`

**验收标准：**
- 中文界面下“当前图片物种”位于“结构标签”上方。
- 其他业务逻辑不受影响。

---

### D10：“结构标签”树高度可伸缩

**位置：** 标注工作台 → 右侧“当前图片”标签页。

**现状：**
- `part_list` 固定高度 190px。
- 外层页面有滚动区，内部树固定高度，容易形成嵌套滚动。

**实现方式：**
1. 将 `part_list.setFixedHeight(190)` 改为：
   - `setMinimumHeight(140)`
   - `setMaximumHeight(300)`
   - 垂直策略改为 `QSizePolicy.Expanding`
2. 在“当前图片”页布局中给 `part_list` 设置 stretch factor，使窗口较高时树能利用空间。
3. 保留树自身的滚动条。

**影响文件：**
- `AntSleap/ui/main_window_shell.py`

**验收标准：**
- 窗口较高时结构树高度随之增加。
- 窗口较矮时结构树不会小于 140px。
- 不再出现右侧页面滚动区内套固定高度树的别扭体验。

---

### D11：快捷键修正

**位置：** 标注工作台。

**现状：**
- 保存绑定为 `QKeySequence(Qt.Key_S)`，实际是裸 `S`，不是 `Ctrl+S`。
- 验证图片绑定为裸 `Space`，容易误触。

**目标：**
- 保存：`Ctrl+S`
- 验证当前图片：`Ctrl+Enter`

**实现方式：**
1. 保存：
   ```python
   self.shortcut_save = QShortcut(QKeySequence.StandardKey.Save, self)
   ```
2. 验证：由“工作流”菜单中的动作“验证当前图片”承载，设置快捷键 `Ctrl+Enter`，避免再创建重复的 `QShortcut`。
3. 菜单动作同时负责触发和快捷键显示，便于用户发现。
4. 新增翻译：
   - `Verify Current Image` → `验证当前图片`

**影响文件：**
- `AntSleap/ui/main_window_shell.py`
- `AntSleap/ui/main_window_presentation.py`
- `AntSleap/ui/main_window_i18n.py`

**验收标准：**
- 焦点在画布上时按 `S` 不再触发保存。
- `Ctrl+S` 正常保存。
- `Space` 不再触发验证。
- `Ctrl+Enter` 验证当前图片。
- 菜单中显示快捷键提示。

---

### D12：移除隐藏的“打开子部位专家会话”按钮

**位置：** 标注工作台 → 顶部工具栏右侧。

**现状：**
- 该按钮创建后始终 `setVisible(False)`，用户不可见，但代码仍维护文案和样式。

**实现方式：**
1. 删除 `btn_blink_entry` 的创建、布局和样式刷新代码。
2. 保留 `launch_blink_from_workbench()` 方法，避免影响其他调用和测试。
3. 更新 `tests/test_ui_polish_scope.py` 中的相关断言。

**影响文件：**
- `AntSleap/ui/main_window_shell.py`
- `AntSleap/ui/main_window_presentation.py`
- `tests/test_ui_polish_scope.py`

**验收标准：**
- 工具栏不再存在该隐藏控件。
- “打开子部位专家会话”相关翻译保留，以备后续功能启用。

---

### D13：为“手动绘制 / 魔棒 (SAM)”补充悬停提示

**位置：** 标注工作台 → 中间工具条。

**现状：**
- “SAM框选分割 / 人工ROI框 / Blink收缩起始框”有 tooltip。
- “手动绘制 / 魔棒 (SAM)”没有。

**实现方式：**
1. 在 `refresh_ui()` 中为两个按钮设置 tooltip，复用现有翻译：
   - `Tool: Manual Draw - Click points to outline.`
   - `Tool: Magic Wand (SAM) - Click to auto-segment.`
2. 中文文案已存在，无需新增。

**影响文件：**
- `AntSleap/ui/main_window_presentation.py`

**验收标准：**
- 鼠标悬停在“手动绘制”和“魔棒 (SAM)”上显示中文提示。

---

### D14：TIF 工作台右侧固定区精简

**位置：** TIF 体数据工作台 → 右侧。

**现状：**
- 右栏固定区同时包含“操作状态”“网格导出”“数据导入”，任务标签页可伸展高度不足。

**目标：**
- 右栏只保留“操作状态”固定区，把空间还给任务标签页。
- 首个标签页明确命名为“导入与预览”，并把“数据导入”放在该页顶部。
- “网格导出”移入“结果对比”标签页顶部。

**实现方式：**
1. 首个标签页由 “Import & Preview / 导入与预览” 固定命名，`import_section` 加入该页 `display_task_layout` 顶部。
2. `mesh_export_section` 加入 `result_compare_layout` 顶部，不再加入 `right_layout`。
3. `right_layout` 只保留 `operation_status_section` 和 `task_tabs`。

**影响文件：**
- `AntSleap/ui/tif_workbench_view_builder.py`
- `AntSleap/ui/tif_workbench_pages.py`
- `AntSleap/ui/tif_workbench_translations.py`
- `AntSleap/ui/tif_workbench.py`

**验收标准：**
- 任务标签页可用高度明显增加。
- 首个标签页“导入与预览”顶部可看到“数据导入”。
- “结果对比”页顶部可看到“网格导出”。
- 按钮行为不变。

---

### D15：TIF 工作台顶部栏显示精简运行状态

**位置：** TIF 体数据工作台 → 顶部栏。

**现状：**
- 顶部只有“TIF 体数据工作台 / 启动中心 / 询问 Agent”。
- 后端运行状态位于右栏“训练与预测”相关区域，切换标签后不可见。

**实现方式：**
1. 在顶部上下文标签后增加 `self.tif_top_runtime_status_label`，使用 muted 样式，文字过长时省略，完整内容放 tooltip。
2. 在 `TifWorkbenchWidget` 中增加统一方法：
   ```python
   def _set_backend_run_status(self, text):
       self.backend_run_status_label.setText(text)
       self.tif_top_runtime_status_label.setText(text)
       self.tif_top_runtime_status_label.setToolTip(text)
   ```
3. 将 `tif_backend_panel_controller.py` 中所有对 `backend_run_status_label.setText()` 的调用改为调用该统一方法。
4. 空闲时显示：`后端运行：空闲` / `Backend run: Idle`；运行中显示状态或进度摘要。

**影响文件：**
- `AntSleap/ui/tif_workbench_view_builder.py`
- `AntSleap/ui/tif_workbench.py`
- `AntSleap/ui/tif_backend_panel_controller.py`
- `AntSleap/ui/tif_workbench_translations.py`

**验收标准：**
- 切换右侧标签时，顶部仍能看到后端运行状态。
- 顶部状态与右栏“后端运行”内容一致。
- 中文界面显示“后端运行：空闲 / 后端运行：...”。

---

### D16：中文文案统一

**位置：** 全局中文界面。

**现状与目标：**

| 现在显示 | 目标 |
|---|---|
| Browser mode is active...（英文） | 当前为浏览器模式。如果浏览器没有自动打开，请打开下面的网址。 |
| Specimen | 标本 |
| TIF specimen | TIF 标本 |
| VLM预标注 | VLM 预标注 |
| VLM批量预标 | VLM 批量预标注 |
| SAM框选分割 | SAM 框选分割 |

**实现方式：**
1. 更新 `AntSleap/ui/main_window_i18n.py` 中相关中文翻译。
2. 更新 `AntSleap/ui/tif_workbench_translations.py` 中 `Specimens` 的翻译。
3. 更新受影响的测试断言：
   - `tests/test_ui_polish_scope.py`
   - `tests/test_gui_smoke.py`
4. 保持英文 key 不变，避免影响英文界面。

**影响文件：**
- `AntSleap/ui/main_window_i18n.py`
- `AntSleap/ui/tif_workbench_translations.py`
- `AntSleap/ui/taxamask_agent_panel.py`
- 相关测试

**验收标准：**
- 中文界面不再出现上述中英混排或英文残留。
- 英文界面不受影响。

---

### D17：沙箱/WSL 下配置目录自动回退

**位置：** 应用启动配置、位置登记数据库、Ultralytics/Matplotlib 缓存。

**现状：**
- 部分 WSL/容器环境里 `/home/用户/.config` 实际不可写。
- 语言、主题等设置保存时报 `PermissionError`，Ultralytics 缓存也写入失败。

**实现方式：**
1. `AntSleap/core/platform_paths.py` 新增 `writable_user_config_dir()` / `writable_user_config_path()`。
2. 标准用户配置目录可写时保持原路径；不可写时回退到 `TaxaMask_outputs/config/`。
3. `ConfigManager` 和 `location_registry` 默认路径改为使用可写版本。
4. `AntSleap/app_runtime.py` 启动早期检测 `YOLO_CONFIG_DIR` 和 `MPLCONFIGDIR` 默认目录，不可写时指向 `TaxaMask_outputs/` 下的对应目录。

**影响文件：**
- `AntSleap/core/platform_paths.py`
- `AntSleap/core/config.py`
- `AntSleap/core/location_registry.py`
- `AntSleap/app_runtime.py`
- `tests/test_config_cleanup.py`
- `tests/test_location_registry.py`

**验收标准：**
- 在 `~/.config` 不可写的 WSL 环境启动时，不再出现 `PermissionError`。
- 语言设置为中文后重启仍为中文。
- 正常 Linux 桌面环境仍使用原 `~/.config/taxamask/` 路径。

---

### D18：WSL 中文字体回退

**位置：** 启动早期环境准备。

**现状：**
- WSL 环境未安装中文字体时，界面切换到中文会显示为空白/方块。

**实现方式：**
1. `AntSleap/app_runtime.py` 在 WSL 下检测 `/mnt/c/Windows/Fonts` 中的 `msyh.ttc / msyhbd.ttc / simsun.ttc`。
2. 字体通过符号链接放入 `TaxaMask_outputs/fonts/`。
3. 生成 `TaxaMask_outputs/fonts/fonts.conf`，包含系统 fontconfig 配置和本地字体目录、本地缓存目录。
4. 启动时设置 `FONTCONFIG_FILE`，使 Qt 在 QApplication 创建前即可使用中文字体。

**验收标准：**
- `fc-list :lang=zh family` 能看到微软雅黑/宋体。
- 中文界面不再显示方块或空白。

---

### D19：TIF 后端 Python 探测容错

**位置：** `AntSleap/core/tif_backend.py`。

**现状：**
- 自动探测 nnU-Net Python 时会扫描 PATH 父目录，包括 `/`。
- 在受限 WSL 环境访问 `/root/bin/python` 会抛出 `PermissionError`，导致进入 TIF 工作台失败。

**实现方式：**
- 新增 `_path_exists()` / `_path_is_dir()`，统一捕获 `OSError`。
- `_resolve_python_path`、`_candidate_python_in_prefix`、`_python_has_nnunet_v2_commands`、候选根遍历全部改用容错版本。

**验收标准：**
- 在无权限访问 `/root` 的 WSL 环境进入 TIF 工作台不再报错。

---

### D20：内嵌模式加载过渡

**位置：** 内嵌 Agent 页面切换。

**现状：**
- `_load_dashboard()` 先切到 QWebEngineView 再加载 URL，会出现空白/深色首帧闪烁。

**实现方式：**
1. 首次加载时继续显示 fallback，直到 `loadFinished(True)` 再切到 WebView。
2. 给 WebView 预设当前主题背景色。
3. 页面失败时仍切回 fallback 并显示“重新加载”。

**验收标准：**
- 内嵌模式启动过程不再先黑一下再显示正常页面。

---

## 4. 兼容性与测试策略

### 4.1 需要同步更新的现有测试
- `tests/test_ui_polish_scope.py`
- `tests/test_gui_smoke.py`
- 其他涉及工具栏父容器、右侧布局顺序、中文文案的测试。

### 4.2 建议新增的回归测试
1. Agent 状态机测试：按钮 enabled 和文案随状态变化。
2. 浏览器重启测试：模拟停止后同端口启动，`open_dashboard_in_browser` 被再次调用。
3. 右侧标签页测试：三个标签存在，训练进度和日志位于“运行与日志”。
4. 快捷键测试：确认序列为 `Ctrl+S` 和 `Ctrl+Enter`。
5. 更多操作菜单测试：菜单动作与隐藏按钮状态同步。
6. TIF 顶部状态测试：右栏状态更新时顶部状态同步。

### 4.3 手工验收场景
- 1920×1080：全部标签和按钮正常。
- 1366×768：右侧三个标签无横向溢出，顶部工具栏不裁切。
- 中文和英文界面各走一遍启动中心 → 标注工作台 → TIF 工作台。
- Linux/WSL 浏览器模式：停止后重启能自动打开浏览器。
- 内嵌模式：故意断开 Dashboard 后能通过“重新加载”恢复。

---

## 5. 实施顺序

1. 第一批（P0）：
   - D01 状态联动
   - D02 浏览器重启修复
2. 第二批（P1）：
   - D03 fallback 浏览器打开按钮
   - D07 右侧标签页
   - D11 快捷键修正
3. 第三批（P2）：
   - D04 重新加载入口
   - D05 上下文再次复制
   - D08 更多操作菜单
   - D14 TIF 首标签页“导入与预览”与数据导入置顶
   - D15 TIF 顶部运行状态
   - D16 中文文案统一
4. 第四批（P3）：
   - D06 fallback 滚动与翻译
   - D09 当前图片物种上移
   - D10 结构树高度
   - D12 移除死按钮
   - D13 工具提示补齐

---

## 6. 评审记录

| 日期 | 评审人 | 结论 | 备注 |
|---|---|---|---|
| 2026-08-16 | 用户 | 校验通过，同意实施 | 按 D01–D16 执行 |
| 2026-08-17 | 用户 | 开发版验收通过 | D01–D20 在 Windows 开发版验收正常 |

---

## 7. 实施记录

| 日期 | 批次 | 状态 | 说明 |
|---|---|---|---|
| 2026-08-17 | P0–P3 + 配置/字体/TIF 容错/加载过渡 | 已验收，随 v2.4.6 发布 | D01–D20 全部完成；`test_gui_smoke` 121 项、`test_ui_polish_scope` 83 项及 TIF 聚焦用例全部通过；TIF 全量 239 项中 3 项为沙箱环境问题（WSL 目录 `os.replace` 限制 1 项、offscreen OpenGL 无有效上下文 2 项），与本次 UI 改动无关；Windows 开发版人工体验复核已通过 |
