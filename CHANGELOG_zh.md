# 中文更新日志

本文档由旧版 README / README_zh 的开发日志迁移而来。根目录现在只保留这一份中文日志和一份详细的大模型对接文件，避免多份文档长期不同步。

## 📅 更新日志 (Update Log)

### **[2026-05-29] TIF GPU 体预览、清晰模式与内部观察闭环**
> **本次重点：在 TIF 体数据工作台内加入只读 3D volume 预览，让研究者可以直接旋转、平移、缩放、进入体内并剖开近端组织观察内部结构，为后续脑部统一方向重切片打基础。**

- 新增可选 OpenGL GPU ray marching 体渲染画布；环境支持时使用 GPU，失败或缺少依赖时自动回退到原 CPU 体预览。
- 新增 `PyOpenGL` 依赖，并加入 `tools/start_antsleap_high_performance_gpu.ps1`，用于在 Windows 上尽量让 Qt/OpenGL 走高性能 NVIDIA 显卡。
- 体预览支持左键旋转、右键平移、滚轮缩放；拖动时使用较低纹理和采样保证交互，停下后自动切回静止高清。
- 新增“清晰模式”，静止高清时可保留 `uint16` 源强度上传 GPU，并提高体纹理最大边长和光线采样上限到 4096，方便观察细小内部结构。
- 新增“视点深度”和“近端剖切”两个控制：前者移动观察点进入体内，后者从当前屏幕近端切除遮挡组织；二者语义已在中文 UI 和 tooltip 中拆开。
- 修正拖动/静止高清纹理切换时比例变化导致体预览变窄的问题；显示比例改为使用原始 TIF `shape_zyx` 与 `spacing_zyx`。
- 右侧栏状态不再常驻挤占日志区域，体预览状态作为画布叠加信息显示，并在中文模式下使用中文指标。
- 程序关闭时主动释放 TIF volume renderer，降低 Qt/OpenGL 退出阶段残留线程提示的概率。
- 当前 3D 体预览仍是只读观察工具，不能直接编辑标签，也还没有实现按标准脑部方向重新切片；脑部统一朝向重采样将作为下一阶段功能在此基础上实现。
- TIF 工作台 `Ask Agent` 上下文补充当前显示模式、切片轴/位置、shape/spacing、train-ready 状态、GPU/CPU 渲染器、清晰模式、视点深度、近端剖切、缩放/平移/视角等字段，便于 Agent 诊断体预览和训练准备问题。
- 新增 `docs/ant3d_workbench/TIF脑部统一朝向重切片需求_zh.md`，把“统一朝向脑切片”整理为可实现需求：手动标定脑区中心、头顶方向和前后方向，按真实 spacing 重采样并裁剪脑部 ROI，图像体与标签体分别采用合适插值。

### **[2026-05-26] VLM 第一公里预标注与 Blink 父级确认修复**
> **本次重点：把多模态大模型接入为“草稿框建议器”，帮助没有训练素材时给 SAM 提供第一批提示框；同时修复新建部位被单一父级自动吸入父子关系树的交互漏洞。**

- 主标注工作台新增 `VLM Pre-Annotate` 入口，可对当前图像或二次确认后的已导入图像线性批量生成 VLM 候选框。
- `2D/STL Model Settings -> Training` 新增 AI 多模态预标注设置；VLM 目标部位由用户从已有部位中勾选，且与主定位部位 `locator_scope` 分开。
- 复用 PDF Evidence 的 Multimodal LLM API 配置；缺少目标部位或 API 配置时，弹窗按钮可直接跳到对应设置位置，API key 输入区保持可见。
- VLM 候选框写入橙色 `aibox`，SAM 草稿 polygon 标记为 `Auto-Annotated`；训练预检跳过未复核草稿，空格确认或当前图像一键通过后才进入训练。
- 当前图像一键通过只确认已有 polygon 的 AI 草稿；纯框候选不会被误认为已复核训练材料。
- 人工重新框选并调用 SAM 时，以人工结果为准，自动移除同部位旧 AI 框元数据和旧草稿。
- 网格图、原始响应、单图 report 和批量 summary 保存在项目同级 `vlm_preannotation/`；源码仓库忽略该运行产物目录，避免真实研究图像和 API 响应误入提交。
- VLM 返回空响应或非 JSON 时，现在会保留 raw response/report 路径，便于排查服务商返回、模型权限或 prompt 输出问题。
- Blink 父级解析不再使用“已有父级框”或“唯一主部位”自动猜测父级；新建部位默认留在未分组结构中，只有用户手动选择父级或已有明确 route 才形成父子关系。

### **[2026-05-26] PDF 多模态复核默认迁移为蚂蚁分类学图版宽松 Profile**
> **本次重点：PDF figure 复核不再以“三视图齐全”为默认目标，而是保留单一蚂蚁物种/单一分类单元的分类学形态图版证据。**

- 默认 Figure Extraction / Review Profile 迁移为 `multimodal_configs/蚂蚁分类学图版宽松复核_示例.json`。
- 内置 profile 现在接受 habitus、侧面、背面、腹面、正面、头部、局部诊断结构、同物种图版组合等多视角/多结构候选；纯局部结构图只要 caption 或附近文本能对应单一蚂蚁物种/分类单元，也可进入 evidence review。
- 多物种或多分类单元比较图默认一律拒绝；地图、系统树、表格、生态/实验图和非蚂蚁主体仍拒绝。
- README、Agentic pipeline contract 和 PDF evidence skill 的默认示例路径同步到新 profile；旧三视图示例不再作为默认或推荐入口保留。
- 研究流程含义：PDF 输出仍是 evidence/candidate/provenance 层，不会自动写入 TIF `manual_truth` 或训练真值；mock/default 复核结果仍进入人工 review，而不是可信 accepted。
- 严格复核后补强 accepted 门槛：真实多模态结果即使返回 `accept=true`，只要 category 属于 comparison/multi/non/other/uncertain，也不会进入 accepted，避免模型 flags 漏打时误收多物种比较图；同时修正用户手册中残留的旧三视图默认说明。
- 新增 PDF 纯文本部位描述结构化链路：提取器在读取全文 `document_blocks` 后，可用 Text LLM 将分类学描述整理为“物种/分类单元 -> 部位 -> 文中描述”，不输入图片，不依赖多模态模型判断小结构。
- 新增独立 Part Description Profile：`part_description_configs/蚂蚁分类学部位描述抽取_示例.json`、`通用分类学部位描述抽取_模板.json`、`植物分类学部位描述抽取_模板.json`。它和图版复核 profile 并列，负责纯文本“部位桶 + 抽取提示词”，不保存 API key。
- PDF Processing 高级设置区新增 `Part Description Profile` 选择、删除和 JSON 编辑入口；headless `tools/agentic/extract_figures.py` 新增 `--part-description-profile`，Agentic pipeline contract 也把它列为独立输入。
- SQLite 新增 `pdf_text_blocks`、`taxon_part_descriptions`、`part_extraction_runs`：前者保存带文件名、文件路径、hash、页码和 block_ref 的原文文本块及 LLM 角色标记；后者保存重点部位描述和来源 block；运行表记录是否 real/mock/skipped/failed，并记录本次使用的部位描述 profile。
- PDF Processing 导出 JSONL 现在附带 `part_descriptions` 字段；GUI 浏览 DB 时会在 figure 证据下方显示同一 PDF/物种相关的部位描述。没有 Text LLM key/model 时，图版提取照常运行，只记录部位描述结构化 skipped。

### **[2026-05-22] 主标注工作台吸收 Blink 父子精修**
> **本次重点：把 2D/STL 日常小部位精修从独立 Blink Workbench 合并回主 Labeling Workbench。研究者在同一张大图里完成父级框、子部位标注、收缩松框、自动标注、trajectory 积累和当前子部位专家训练；独立 Blink widget 保留为兼容回退。**

#### **0）Ask Agent 上下文路由表**
- 新增 `AntSleap/core/agent_context_routes.py`，把固定 `Ask Agent` 入口映射到对应的大模型对接文件章节、源码/契约文件、产物检查提示、诊断重点和安全边界。
- `MainWindow._compact_agent_context()` 现在会先调用路由表增强上下文，再按白名单和总长度限制压缩，避免把长文档、完整命令、项目大 JSON 或敏感配置整段塞进对话框。
- `TaxaMaskAgentPanel._context_prompt()` 新增显示 `diagnostic_route`、`diagnostic_focus`、`llm_context_refs`、`source_code_refs`、`artifact_hints`、`safety_notes` 和 `suggested_agent_action`。
- 如果设置页里存在“命令已填写但缺少 `{contract}` / `{contract_json}`”这类常见问题，诊断路线会自动标记为 contract 占位符缺失，Agent 可以直接优先检查外部后端命令模板。
- 研究流程含义：`Ask Agent` 现在传的是“短索引卡片”，告诉 Agent 该读哪几段文档、哪几个源码/契约和哪些运行产物；它不再只是粗略字段摘要，也不会把大量内容复制进聊天框。

#### **0.1）TaxaMask Agent 分级写入授权**
- `denyTaxaMaskSourceWrites` 从单纯源码只读拦截升级为 TaxaMask 分级门禁：普通读取/诊断不弹窗，外部模型后端适配走轻确认，TaxaMask 源码开发走强确认。
- 新增 `taxamask.adapter` 与 `taxamask.source_development` 两类专用审批。hook 命中受保护写入时先触发 Dashboard 审批；用户批准后，同一次工具调用会带着 TaxaMask 专用授权标记重新通过 hook。
- `external_backends/`、`external_backend_adapters/`、`model_backends/` 和 `.tmp_validation/external_backends/` 被视为外部模型适配区；`AntSleap/`、`core/`、`tools/`、`tests/` 与 `vendor/ant-code/src|tests|scripts` 仍属于源码开发强确认区。
- `ANTCODE.md`、TaxaMask workflow skill 和 Ant-Code 初始上下文同步补充提示词规则：智能体应优先尝试外部后端契约/配置适配；只有契约或设置面不足时，才说明原因并申请源码开发。
- 研究流程含义：对接新 TIF 或 2D/STL 自定义模型时，用户会明确知道“这是改外部后端适配”还是“这是改 TaxaMask 程序本身”，并在真正写入前确认风险。

#### **1）2D/STL 日常入口收口到主标注工作台**
- 2D/STL 模式现在日常只显示 `Labeling Workbench`。
- 顶部旧 `Open in Blink Workbench` 入口已隐藏，独立 Blink tab 不再作为普通标注流程入口。
- 旧 `BlinkLabWidget`、旧启动函数和训练线程保留，作为兼容与开发回退，避免一次性删除后端训练链路。

#### **2）右侧新增父子精修 / Blink 区**
- 主工作台右侧新增 `Parent-child refinement / Blink` 小区。
- 该区域显示当前部位角色、当前 `parent -> child` 路由、父级上下文、父级框状态和路由专家状态。
- 新增父级上下文下拉框，用户可手动把子部位绑定到正确父部位；选择会写入项目记忆 `blink_context_roi_parents`。
- `Configure Route Expert` 可直接打开设置里的项目路由专家配置，并定位当前父子 route。

#### **3）框角色拆清楚**
- 新增主画布 `Annotation Box` 模式。
- 父部位的 annotation box 继续写入原有 manual box，同时作为子部位精修的父级上下文框。
- 子部位 annotation box 写入子部位正式框，不继承父部位固定比例。
- 收缩松框写入新增 `shrink_loose_boxes` 字段，不覆盖子部位正式框。
- `Box Prompt (SAM)` 仍然只是 SAM 临时提示，不写入正式框角色。

#### **4）父级框支持固定长宽比**
- 项目新增 `parent_box_aspect_ratios`，默认包括 `Head=1.0`、`Mesosoma=4/3`、`Gaster=4/3`、`Whole body=16/9`。
- `2D/STL Model Settings` 中可编辑父级框比例。
- 主工作台可通过 `Lock parent box ratio` 临时解除比例锁定。

#### **5）自动标注、自动收缩、专家训练都使用当前父子上下文**
- `Auto-annotate child` 使用当前父级框和项目 route manifest 调用 route-appointed expert，再由基础 SAM 生成子部位草稿 polygon。
- `Run auto-shrink` 使用当前子部位 polygon 和 `shrink_loose_boxes` 生成 trajectory，并保存 `parent_context`。
- `Train current child expert` 复用现有 Blink 训练线程和 route candidate 注册逻辑，但入口来自主标注工作台当前父子上下文。
- 兼容 Blink 回退界面不再展示或响应空格键 Blink 切换提示，避免和主工作台的空格验证快捷键混淆。
- 研究流程含义：用户不再需要理解局部会话、坐标映射和 `Apply to Global` 才能完成常见小部位标注。

### **[2026-05-17] Agent Center 启动页 + TIF/STL 分流 + 模型惰性加载 + 文档/skill 收口**
> **本次重点：把 TaxaMask 的真实入口从旧的工作台优先路线收口为 Agent Center 优先路线；2D/STL 与 TIF 明确分成两个工作流；PDF 下沉为 evidence/Agent 任务；Locator/SAM 改为进入 2D/STL 时才预加载；同时同步使用手册、README、LLM 对接文件和项目本地 skill。**

#### **1）启动中心成为 TaxaMask Agent Center**
- 启动页主区域现在承载内嵌 Ant-Code Dashboard，作为自然语言配置、排错、PDF 任务规划和训练准备检查入口。
- 右侧栏上下排列两个主要工作流入口：
  - `2D/STL Morphology`
  - `TIF Volume`
- 工作台界面只保留轻量 `Start Center / Ask Agent` 入口，避免聊天窗口挤占标注画布、Blink 工作区或 TIF slice viewer。
- 从工作台回到 Agent Center 时会携带当前项目、工作台、active image/specimen、材料层或部位、最近日志等上下文，减少用户重复描述现场。

#### **2）Ant-Code 集成边界固定为分发版嵌入**
- TaxaMask 调用 `lab-agent` 的分发版 `ant-code.exe`，而不是把 `lab-agent` 源码复制进项目或实现弱化聊天助手。
- 默认工作区是当前 TaxaMask 仓库。
- TaxaMask 嵌入视图只显示 Ant-Code 的中间对话/任务区域，隐藏 Ant-Code 原生左右栏，避免启动页拥挤。
- `.lab-agent/memory.md` 作为短项目记忆保留；`.lab-agent/sessions/`、任务缓存和运行痕迹继续忽略，不进入版本历史。

#### **3）2D/STL 与 TIF 工作流边界重新明确**
- 2D/STL 工作流继续使用现有 Labeling Workbench、Blink、Locator/SAM、route-appointed experts 和 2D external backend。
- STL 当前指“已经从 STL/mesh 渲染出的固定视角 2D 图”，导入后注册到 Labeling Workbench；不是直接 3D mesh 涂色工作台。
- TIF 工作流使用独立 TIF 项目、AMIRA-style material ID、slice viewer、material map、`working_edit`、`manual_truth`、`model_draft` 和 TIF backend contract。
- TIF 后端配置独立于 2D/STL 模型设置，可对接 nnU-Net、MONAI 或自定义体分割脚本，但不写死为某一个模型家族。

#### **4）PDF 下沉为 evidence / Agent skill 路线**
- PDF Processing 不再作为主界面第一视觉入口。
- PDF 处理保留为 `File -> Open PDF Evidence Tools` 和后续 Agent skill/headless workflow。
- PDF 输出只作为 literature evidence、candidate 和 provenance；不会自动成为 TIF `manual_truth` 或 2D/STL 正式训练真值。

#### **5）Locator / SAM 改为按工作流惰性加载**
- 程序启动到 Agent Center 时不再默认加载 Locator 或 SAM。
- 进入 TIF 工作流时也不加载 Locator/SAM。
- 进入、打开或导入 2D/STL 工作流时才预加载 Locator 和 SAM。
- 一旦加载后，切回 Agent Center 不卸载，方便在 2D/STL 和 Agent 间来回排错或配置。
- 研究流程含义：只处理 PDF、TIF 或配置排错时不再一启动就占用显存和等待 SAM 初始化。

#### **6）文档与项目 skill 同步**
- `README.md` 同步为当前公开入口：Agent Center、2D/STL、TIF、PDF evidence 和惰性模型加载。
- `TaxaMask使用手册.md` 大幅更新：新增当前版本先读、Agent Center 使用方式、TIF 专章、设置分流、TIF 导出和 TIF 常见误区。
- `LLM_CONTEXT_DETAILED.md` 同步到 v3.24，记录当前 Agent/TIF/STL/PDF/模型加载边界。
- 新增 `ANTCODE.md`，作为 TaxaMask 内嵌 Agent 的最高优先级常驻项目规则；同时新增 `.lab-agent/skills/taxamask-workflows/SKILL.md`，作为始终相关的短上下文工作流 card。完整手册仍是权威长文档，skill/card 只提供入口索引、常见流程和安全边界。
- 已验证 Ant-Code 项目记忆 loader 在当前仓库中选择 `ANTCODE.md` 作为 active rule，并把同级 `AGENTS.md` 放入 skipped rules；因此 `ANTCODE.md` 已镜像关键协作、Git、文档和研究数据安全规则。

### **[2026-05-13] Windows/Linux/macOS 源码适配落地 + 路由缺文件历史清理**
> **本次重点：按 Windows 和 Linux 为主、macOS 仅 CPU-only 源码试用的策略，完成跨平台路径、配置、Poppler 检测、GUI smoke 与项目搬盘恢复工具；同时修复项目路由树里 Blink 专家“缺文件历史”无法清理的问题。README 已明确回到 GitHub 首页展示/安装文档定位，历史记录继续集中在本 changelog。**

#### **1）README 与公开平台定位收口**
- `README.md` 保持为 TaxaMask 的公开 GitHub 首页展示与安装入口，不再作为开发日志使用。
- 公开产品名统一为 `TaxaMask`；内部 Python 包名 `AntSleap` 暂时保留，用于稳定现有导入路径和历史兼容。
- 平台说明改为：
  - Windows 10/11：当前验证最充分的桌面入口。
  - Linux：本轮主要跨平台目标，适合实验室工作站、服务器、CUDA 训练和批处理。
  - macOS：仅作为 CPU-only 源码轻量试用路径，用于项目检查、标注整理、教学和小规模 smoke test。
- Apple Silicon MPS 不进入第一轮支持目标；高级用户可自行尝试适配 PyTorch/SAM 组合，但 TaxaMask 不把 MPS 暴露为受支持运行设备。

#### **2）跨平台配置与文件打开**
- 新增 `AntSleap/core/platform_paths.py`，运行时配置迁移到系统用户配置目录：
  - Windows：`%APPDATA%/TaxaMask/user_config.json`
  - Linux：`~/.config/taxamask/user_config.json` 或 `$XDG_CONFIG_HOME/taxamask/user_config.json`
  - macOS：`~/Library/Application Support/TaxaMask/user_config.json`
- 仓库根目录旧 `user_config.json` 只作为首次迁移来源；程序复制后保留旧文件，不自动删除。
- 新增 `AntSleap/core/platform_open.py`，报告文件夹打开逻辑改为 Windows/macOS/Linux 分支封装，避免训练报告 UI 写死 Windows 行为。

#### **3）运行设备策略固定为 CUDA 优先，否则 CPU**
- `AntSleap/core/runtime_device.py` 明确只支持 `auto / cpu / cuda`。
- `auto` 在 PyTorch 报告 CUDA 可用时选择 CUDA，否则选择 CPU。
- 没安装 PyTorch 的轻量环境也能导入该模块，并安全解析为 CPU，便于文档、路径和 GUI smoke 测试。
- Model Settings 中不暴露 MPS 选项，避免研究者误以为 Mac GPU 训练链路已经验证。

#### **4）PDF / Poppler 检测可见化**
- 新增 `core/pdf_processor/poppler_discovery.py`，统一发现：
  - 用户配置路径
  - 仓库 `external_tools/poppler`
  - 系统 `PATH`
- PDF OCR / `pdf2image` fallback 使用统一发现逻辑。
- PDF Processing 页面新增 Poppler 状态提示；缺 Poppler 时明确说明 PyMuPDF 提取仍可运行，但 OCR/image fallback 可能不可用。
- 研究流程含义：PDF 失败时能更快区分“系统依赖缺失”和“API/模型问题”，减少误判。

#### **5）项目搬盘后的图片路径健康检查与重定位**
- `ProjectManager` 新增图片路径健康检查、重定位预览和确认后 remap：
  - `get_image_path_health()`
  - `preview_image_path_remap(...)`
  - `apply_image_path_remap(...)`
- 主菜单新增 `File -> Check / Relocate Project Images`。
- 该工具只处理当前项目中缺失的图片路径，并且只接受新根目录下唯一文件名匹配；同名图片多份时保持未解决，避免把标注错连到另一张标本图。
- 中文手册同步为优先使用 GUI 检查/重定位；`known_relocated_roots` 保留为高级兜底配置。

#### **6）Blink 路由缺文件历史可清理**
- 路由树中第三层专家节点仍保留不同状态：
  - `Appointed`
  - `History`
  - `Missing file history`
  - `Discoverable`
  - `Available`
- 新增 `ProjectManager.remove_cascade_route_expert_candidate(...)`。
- 当选中的是 `Missing file history` 且不是当前 appointed 专家时，路由管理面板的 `Delete` 可以清理这条失效历史。
- 该操作只清理当前项目 route 的 `expert_candidates` 历史记录，不删除任何磁盘模型文件，也不改变当前指定专家。
- 研究流程含义：如果 Blink 里已经删掉某个专家模型，Model Settings 路由树里残留的缺文件历史可以直接清掉，不必再绕回 Blink 专家列表。

#### **7）跨平台 smoke 与验证矩阵**
- 新增 `.github/workflows/cross-platform-smoke.yml`，覆盖 Windows / Linux / macOS 的轻量 CI。
- 新增 `docs/platform_setup.md`，记录安装顺序、Poppler、Linux GUI、运行设备策略、项目搬盘和验收矩阵。
- 新增或扩展测试：
  - `tests/test_config_cleanup.py`
  - `tests/test_platform_open.py`
  - `tests/test_poppler_discovery.py`
  - `tests/test_runtime_device.py`
  - `tests/test_gui_smoke.py`
  - `tests/test_generic_export_schema.py`
  - `tests/test_locator_scope.py`
  - `tests/test_ui_localization.py`
  - `tests/test_window_geometry.py`
- 本地验证包括基础环境轻量测试、`antsleap` 维护者测试环境 GUI smoke、Poppler / runtime device / project remap / route missing history 定向测试。

### **[2026-05-12] 训练工作流与 Blink 专家路线收口**
> **本次重点：围绕开源前的真实研究使用流程，补齐主工作台训练控制、Blink 专家训练可调参数、训练报告、专家候选与路由指定机制。`best_expert.pth` 从当前 Blink 专家工作流中退场，改为“版本化候选模型 + 项目路由指定专家”的可审计机制。**

#### **1）主工作台训练控制增强**
- 标注工作台右侧训练区新增 `Stop Training / 停止训练` 按钮。
- Locator 和 SAM 训练循环现在会在 epoch / batch 边界响应中断请求，避免训练跑起来后只能等待自然结束。
- 新增 `Train Locator only (skip SAM) / 仅训练定位器（跳过 SAM）` 选项。
- 研究流程含义：当基础 SAM 已经足够好，只想继续强化主定位器时，可以跳过 SAM/parts 训练，减少时间和显存占用。
- 训练日志面板加高，并让右侧工作台面板通过滚动和伸展策略保持可读，不再把日志挤成很小一块。

#### **2）模型设置窗口适配长配置**
- `Settings -> Model Settings` 改为更矮的初始窗口，并让 Training / Inference / External Backend 标签页内部滚动。
- 修复 27 寸屏幕仍可能点不到底部保存按钮的问题。
- 多个下拉框改为 `NoWheelComboBox`，避免鼠标滚轮经过模型选择、导出格式、Blink 入口 ROI 等控件时误切换选项。
- Training 标签页新增 `Runtime Device / 运行设备`，可选择 `Auto / CPU only / CUDA GPU`。
- 该选项现在统一影响内置 Locator、SAM、Blink 专家训练与推理；CPU 路径用于无显卡机器的小规模验证和标注整理，正式训练仍建议 CUDA。
- 严格复核时补齐 Blink 自动收缩轨迹生成的设备链路，旧的 `BlinkRefiner` 默认 `cuda` 已改为跟随当前运行设备设置。
- 复核并记录当前跨平台状态：Windows 是当前验证最充分的平台；Linux / macOS 具备一定代码基础，但在开源说明中应先标为实验性支持，后续需要实机验证 Qt、PyTorch、Poppler 和文件打开行为。

#### **3）Blink 专家训练参数开放**
- Model Settings 新增 Blink 专家训练默认值：
  - 默认 Blink epochs
  - 默认 Blink batch size
  - 默认 Blink learning rate
  - 默认 Blink weight decay
  - 默认 Blink input size
- Blink 工作台训练区同步显示这些默认值，同时仍允许单次训练前临时调整。
- Blink 输入尺寸开放为稳定预设值 `224 / 384 / 512`，避免任意尺寸导致 ViT patch embedding 或显存行为不可控。
- `MicroExpertLocator` 支持按输入尺寸初始化；非 224 预训练 ViT 会对 position embedding 做插值适配。

#### **4）Blink 训练过程可见、可中断、可复盘**
- Blink 工作台新增训练进度条和 `STOP TRAINING / 停止训练` 按钮。
- Blink 训练线程现在支持日志流、进度回调、停止回调和训练取消状态。
- Blink 训练结束后生成报告：
  - `training_log.csv`
  - loss 曲线图
  - 验证样本预测框对比图
  - validation index
  - summary JSON
- 报告弹窗展示摘要、指标图和框验证图，帮助用户判断新专家是否值得指定到路由。

#### **5）Blink 新训练不再写入 `best_expert.pth`**
- Blink 专家训练现在保存为 `expert_vYYYYMMDD_HHMMSS.pth` 形式的版本化候选模型。
- 单次训练内部仍保存本轮 loss 最好的 checkpoint，但文件名不再暗示它一定优于历史所有专家。
- 研究流程含义：新训练结果默认只是候选，用户可以结合训练报告和实际自动标注效果决定是否指定到当前路由。

#### **6）路由指定专家成为唯一当前使用入口**
- Blink 当前路由和 Model Settings 项目路由管理共用同一套 route manifest。
- 如果当前 `父部位 -> 子部位` 路由已有指定专家，新训练只加入候选列表，不会自动覆盖用户已经认可的专家。
- Blink 工作台里的 `Appoint to Current Route / 指定到当前路由` 只更新项目路由，不复制、不改名、不覆盖模型文件。
- Blink 自动草稿现在要求当前父部位 ROI 与子部位之间存在路由指定专家；找不到指定专家时会提示先训练候选或手动指定。
- Blink 左下角专家树按版本化 `.pth` 文件展示，并通过悬浮提示显示完整 `部位/模型文件名` 和磁盘路径。
- 已训练专家列表新增 `Edit Note / 编辑备注`，用于给候选专家添加“侧面稳定”“小样本可用”等人工记忆标签。
- 备注保存到 `weights/experts/expert_notes.json`，只影响 Blink 专家树和项目路由树的展示，不会重命名 `.pth` 文件，也不会改变 route manifest 里的真实 `expert_id`。
- 删除单个专家文件或整个子部位专家桶时，会同步清理对应备注，避免旧标签继续指向不存在的模型。

#### **7）保留旧项目兼容，但不作为新流程默认**
- `best_expert.pth` 只保留为旧版全局 cascade manifest 的兼容文件名。
- 当前 GUI 训练、候选列表和自动标注都不再依赖 `best_expert.pth` 作为默认专家。
- `LLM_CONTEXT_DETAILED.md` 已同步为“route-appointed expert / 路由指定专家”语义。

#### **8）测试与修复**
- `tests/test_blink_bridge.py` 覆盖 Blink 入口父子 ROI 记忆、候选专家、路由指定、删除专家桶、训练线程参数、手工提示框取消等路径。
- `tests/test_locator_scope.py` 增加“新训练候选排到前面但不覆盖既有指定专家”的断言。
- `tests/test_macro_micro_pipeline.py` 更新为版本化专家文件名和路由指定专家语义。
- 修正旧测试替身缺少 `_current_part_name()`、旧弹窗 mock 不再匹配主题确认弹窗的问题。

### **[2026-05-05] 多物种适配链路收口 + 主定位结构 UI + agentic 合约对齐**
> **本次重点：把“可配置多类群”从 PDF 处理、标注训练、Blink/外部后端说明延伸到大模型自动化合约，并修正文献处理页 API 区在窗口缩放时的布局问题。当前结论是：架构和用户入口已打通，蚂蚁仍是验证最充分示例，其他类群需要通过 profile 小批量试跑完成实证落地。**

#### **1）Model Settings 新增主定位结构选择**
- `Settings -> Model Settings -> Training` 新增 `Main Locator Parts / 主定位结构`。
- 该控件直接编辑项目 `locator_scope`，决定内置 Locator 学哪些大而稳定的主结构。
- 小结构仍可保留在 `Structures` 中，后续由 SAM、Blink 专家或外部脚本后端精修。
- 保存后如果 Locator 输出头与当前 `locator_scope` 不匹配，程序会沿用既有逻辑提醒重新训练或选择匹配模型。

#### **2）agentic / 大模型自动化合约对齐 PDF Processing**
- `AntSleap/config/agentic_pipeline_contract.json` 新增 `screener_config` 和 `figure_profile` 输入。
- 文献筛选阶段现在显式传入 `--config {screener_config}`。
- 图文提取与多模态复核阶段现在显式传入 `--figure-profile {figure_profile}`。
- 默认示例仍保留蚂蚁路径，便于用户参考已验证工作流；通用/植物/自定义类群可替换 profile。
- `tools/agentic/run_agentic_pipeline.py` 新增 `--screener-config` 和 `--figure-profile` 覆盖参数。

#### **3）agentic 阶段依赖和产物路径修正**
- `run_agentic_pipeline.py` 支持 contract 中的 `required_artifacts`。
- 后续阶段会等待 `routing_decisions.json`、`pdf_candidates_raw.json`、`project_agentic_import.json` 等上游产物真实存在后才变为 runnable。
- 修正 figure extraction 合约输出路径：figure 图片和 review batch 实际位于 `<db parent>/<db stem>_v2_artifacts/` 下，而不是 `output_dir/figure_extraction/`。

#### **4）PDF Processing 布局修复**
- 修正文献处理页在原始窗口或全屏窗口下 API 输入框被压扁的问题。
- 页面改为滚动承载，窗口较小时滚动而不是压缩顶部 API 区。
- Text LLM 和 Multimodal LLM 输入框/下拉框保留可用高度。

#### **5）用户手册与大模型对接文档同步**
- `docs/Formica_flow使用手册.md` 补充 `Main Locator Parts` 的研究流程含义和使用建议。
- `Validate External Backend` 从 PDF 处理页按钮速查移动到 Model Settings 速查。
- `docs/PDF筛选profile适配说明.md` 修正过时 CLI 示例参数。
- `LLM_CONTEXT_DETAILED.md` 更新到 v3.20，记录 locator scope UI、agentic profile 输入和 artifact gating。

#### **6）测试与验证**
- `tests/test_agentic_contract.py` 扩展 agentic profile 输入、figure artifact 路径和 required artifact gating 测试。
- `tests/test_ui_polish_scope.py` 增加 API 输入框窗口缩放几何测试和主定位结构 UI 测试。
- 验证通过：
  - `python -m py_compile tools/agentic/run_agentic_pipeline.py AntSleap/ui/pdf_processing_widget.py AntSleap/main.py`
  - `python -m unittest tests.test_agentic_contract`
  - 受影响 UI 测试：主定位结构、PDF API 输入框缩放、旧 cascade 总开关移除断言。

### **[2026-05-03] 标注工作台通用物种适配 + 外部脚本后端闭环**
> **本次重点：把标注工作台从“界面和导出仍明显偏蚂蚁历史项目”整理为 TaxaMask 的通用分类学掩码工作台，同时增加外部脚本后端，让高级用户可以把自己的训练/推理脚本接入“标注 -> 训练 -> 自动预标注 -> 复核 -> 再训练”的闭环。**

#### **1）导出 schema 和数据字段完成通用化**
- COCO 导出不再默认写死 `supercategory = ant_part`，新默认是 `biological_structure`，也支持项目级 `category_supercategory`。
- Multimodal JSONL schema 改为 `taxamask-multimodal-sample-v1`。
- Multimodal JSONL 新增 `taxon`、`taxon_rank`、`taxon_metadata`、`annotation_status`、`review_status`。
- 旧字段 `genus` 暂时保留，避免旧项目和旧下游脚本突然断裂。
- YOLO `dataset.yaml` 类名写出增加引号保护，降低空格、冒号等结构标签名造成下游 YAML 解析问题的风险。

#### **2）Taxon 元数据兼容层落地**
- 项目标签现在以 `taxon` 作为通用分类单元字段。
- 旧项目只有 `genus` 时，读取后会兼容为 `taxon`。
- `get_genus()` / `set_genus()` 保留为兼容包装，主界面改用 `get_taxon()` / `set_taxon()`。
- 研究流程含义：`taxonomy` 是要标注的结构标签，例如 Head、Leaf、Flower；`taxon` 是这张图对应的分类单元，例如 Formica、Quercus。

#### **3）UI 名称和默认项目入口改为 TaxaMask**
- 窗口标题改为 `TaxaMask Workbench`。
- 自动创建的占位项目名改为 `TaxaMask_Project`。
- 右侧元数据区把 `Taxon / 分类单元` 和 `Structures / 结构标签` 分开显示，避免把分类单元和结构标签混在一起。
- 内部包名 `AntSleap` 不改，以保护现有导入、历史项目和开发路径。

#### **4）新增项目模板**
- 新增 `AntSleap/core/project_templates.py`。
- 内置模板：
  - `Generic taxonomy mask project`：`Object / Region / Structure`，Locator scope 默认 `Object`。
  - `Ant morphology (validated example)`：`Head / Mesosoma / Gaster`，保留当前验证最充分的蚂蚁示例。
- GUI 新建项目时会选择模板；UI 默认推荐通用模板。
- `ProjectManager()` 无参内部默认仍保留蚂蚁三部位，避免破坏旧测试、旧 Blink 路由和旧项目逻辑。

#### **5）路径恢复逻辑改为本地配置，不再写死作者机器路径**
- 核心代码不再内置 `C:\savedata\Formica-Flow_output` 这种作者本机路径。
- 新增 `known_relocated_roots` 配置入口，用于本地声明旧路径 marker 到新根目录的映射。
- 对开源用户来说，新项目不会被固定到作者个人目录；对旧项目来说，仍可通过本地配置恢复搬盘后的图片路径。

#### **6）外部脚本后端适配层落地**
- 新增 `AntSleap/core/external_backend.py`。
- 新增契约文档 `docs/contracts/external_backend_contract_v1.md`。
- 标准契约包括：
  - `taxamask_external_backend_contract_v1`
  - `taxamask_prediction_v1`
  - `taxamask_model_manifest_v1`
- 外部后端运行时会创建独立 `external_runs/<timestamp>_<action>_<backend_id>/`，写入 `contract.json`，并捕获 stdout / stderr 日志。
- 预测结果只导入当前项目 taxonomy 中存在的标签，默认不覆盖人工标注。
- 选择外部后端时：
  - 训练不会启动内置 `TrainingThread`
  - 推理不会调用内置 `predict_full_pipeline()`
  - 不会把外部模型混入内置 `weights/locator_*.pth` 或 `weights/sam_decoder_lora_*.pth`

#### **7）外部后端 UI 调整**
- `Settings -> Model Settings` 的最后一个标签页新增 `External Backend`。
- 外部命令改为多行编辑区，方便审查、临时修改和复制长命令。
- 页首新增说明：外部后端是高级入口，通过 `{contract}` 或 `{contract_json}` 接收契约 JSON；选择该后端时内置 Locator/SAM 会让位。
- 新增 `Validate External Backend` 校验按钮，保存时也会检查：
  - 外部后端 ID 不能为空
  - 至少填写训练命令或推理命令
  - 已填写命令必须包含 `{contract}` 或 `{contract_json}`

#### **8）测试与验证**
- 新增通用类群工作流测试 `tests/test_generic_taxonomy_workflow.py`。
- 扩展 `tests/test_generic_export_schema.py`，覆盖模板、taxon 兼容、导出 schema、路径恢复配置、外部训练/推理 dummy backend。
- 验证通过：
  - `python -m pytest tests\test_generic_export_schema.py tests\test_generic_taxonomy_workflow.py tests\test_locator_scope.py tests\test_agentic_multimodal_export.py tests\test_api_runtime_settings_schema.py`
  - 结果：`30 passed`
- 编译检查通过：
  - `python -m compileall AntSleap\core AntSleap\ui AntSleap\main.py tools\agentic\export_multimodal_dataset.py`

### **[2026-05-03] 图文提取与多模态复核 profile 化 + 双 API 角色设置**
> **本次重点：把 PDF 后半段的 figure 提取、证据组装和多模态复核从“蚂蚁三视图写死逻辑”改成可配置 profile，同时把文本模型和多模态模型的 API 设置分开。**

#### **1）新增 Figure Extraction / Review Profile**
- 新增 `multimodal_configs/` 目录。
- 新增 `蚂蚁三视图提取复核_示例.json`、`通用分类学图版提取复核_模板.json`、`植物分类学图版提取复核_模板.json`。
- 图文提取阶段现在可以通过 profile 调整 caption 识别、分类学证据词、核心/扩展章节、期望视图或结构。

#### **2）多模态复核不再固定蚂蚁三视图**
- `core/pdf_processor/multimodal_validator.py` 现在读取 figure profile 的 prompt、category、视图/结构字段和 mock 回退规则。
- 蚂蚁三视图保留为默认示例；通用和植物模板不再继承 `lateral / dorsal / head_frontal` 作为强制接受条件。

#### **3）PDF Processing 顶部新增下游 profile 入口**
- GUI 顶部现在区分 `Select Logic Profile` 和 `Figure Extraction / Review Profile`。
- 前者管 PDF 文献筛选，后者管 figure 提取、证据组装和多模态复核。
- `Advanced Figure Settings` 提供 JSON 编辑入口，方便复制模板后改成其他类群。

#### **4）API 设置拆成 Text LLM 和 Multimodal LLM**
- Text LLM API 用于 PDF 文本筛选。
- Multimodal LLM API 用于图像 + 文本复核，可选择复用 Text LLM provider，也可单独填写视觉模型。
- `screener_configs/api_runtime_settings.example.json` 更新为 v2 结构，不包含真实 key。

#### **5）CLI 与测试同步**
- `tools/agentic/extract_figures.py` 新增 `--figure-profile`，并兼容 `--multimodal-profile` 别名。
- 新增 `tests/test_figure_profile.py` 和 `tests/test_api_runtime_settings_schema.py`。
- 已通过新增 profile 测试、API runtime schema 测试，以及关键 agentic/config 回归测试。

### **[2026-05-03] PDF 筛选跨物种 profile 接口修正 + V2 示例模板补齐**
> **本次重点：确认新版 PDF 文献处理仍保留可修改筛选逻辑和提示词的接口，并修掉 V2 路径中会把其他类群筛选暗中拉回“蚂蚁新种报道”的硬编码补充。**

#### **1）V2 不再在程序内部追加蚂蚁专用判定标准**
- `core/pdf_processor/pdf_classifier.py` 中批量 LLM 校验仍会追加 record_id 和 JSON 完整性硬约束。
- 但“include / exclude / uncertain 到底代表什么生物学目标”现在完全以当前 profile 的提示词为准。
- 对研究流程的意义是：当 profile 改成植物、甲虫或其他类群时，模型不会再被程序末尾的蚂蚁提示词带偏。

#### **2）新增 V2 profile 示例和模板**
- 新增 `screener_configs/蚂蚁新种筛选_V2示例.json`，作为蚂蚁分类学参考示例。
- 新增 `screener_configs/通用分类学新种筛选_V2模板.json`，作为其他类群适配起点。
- 新增 `screener_configs/植物分类学新种筛选_V2模板.json`，作为植物分类学示例起点。

#### **3）高级逻辑设置界面现在能编辑 system prompt**
- `AntSleap/ui/pdf_processing_widget.py` 的 Advanced Logic Settings 现在显示 `llm_system_prompt`。
- 关键词词库在 V2 中也可以直接展开查看和编辑，不再被界面文案误导成只属于 Legacy。

#### **4）新增 PDF profile 适配说明**
- 新增 `docs/PDF筛选profile适配说明.md`。
- 说明了每个字段在做什么、为什么影响筛选结果，以及如何从蚂蚁示例改成其他类群。

#### **5）移除用户可见的 Legacy / V1 PDF 筛选回退**
- PDF Processing 界面不再显示 `Legacy (Rule Prefilter)` 模式。
- 删除旧的 `screener_configs/默认Legacy方案.json`，避免用户误用蚂蚁历史规则作为跨类群筛选入口。
- `batch_classify()` 现在面向用户流程固定走 V2。

### **[2026-04-27] Agentic 无界面流水线接入 + PDF 候选追溯 + 批处理验证**
> **本次重点：把旧测试版中已经跑通的 agent 模块正式接入当前最新版，让智能体可以通过命令行编排 PDF 筛选、figure 提取、候选治理、项目导入、自动标注、训练烟测和多模态导出，同时不改变原有人类 GUI 交互路径。**

#### **1）新增 `tools/agentic/` 独立编排层**
- 仓库现在新增一组 headless CLI：
  - `screen_pdfs.py`
  - `extract_figures.py`
  - `import_candidates_to_project.py`
  - `auto_annotate_project.py`
  - `train_project.py`
  - `export_multimodal_dataset.py`
  - `run_agentic_pipeline.py`
- 同步新增 `AntSleap/config/agentic_pipeline_contract.json`，用于让代码智能体读取阶段、输入、输出和质量门。
- 对研究流程的意义是：以后智能体不需要模拟点击 Qt 界面，而是直接调用稳定命令、读取 JSON/run index，并把异常 PDF、候选图片和导出数据留成可复核产物。

#### **2）项目 JSON 增加图片来源追踪，但不改变人工标注结构**
- `ProjectManager` 现在支持 `image_provenance`、`set_image_provenance(...)` 和 `get_image_provenance(...)`。
- 从 PDF 候选导入的图片会记录来源 PDF、页码、figure/candidate id、治理路由状态等信息。
- 多模态导出的 JSONL 样本现在会带 `source_provenance`，方便之后追溯训练数据来源。
- 旧项目没有 `image_provenance` 也能正常读取；人工打开项目、手动标注、保存、训练的主 GUI 路径没有改写。

#### **3）PDF 相关依赖现在更适合 agent 批处理环境**
- `core/pdf_processor` 对 `openai`、`pdf2image` 等可选依赖做了降级处理。
- 缺少 LLM SDK 时，不会让整个 PDF 模块导入失败；真正需要 LLM 筛选时再进入明确的降级或人工复核状态。
- 对研究流程的意义是：轻量环境下仍可运行候选导入、项目导出、单元测试等非 LLM 阶段，不会因为一个外部 API 依赖缺失而阻断全部流程。

#### **4）候选导入默认保持 `needs_review`，不会自动进入可信训练集**
- `import_candidates_to_project.py` 新增 `--status needs_review` 默认语义。
- 经治理后若仍属于 `Ambiguous` 或低置信候选，不会被静默当成可信标注或训练样本。
- 对研究流程的意义是：PDF 里抽出的地图、曲线图、分布图或不标准形态图，可以进入项目等待复核，但不会污染训练数据。

#### **5）使用旧测试 PDF 批次完成接入验证**
- 测试 PDF 目录：`E:\test-project\LBJ-workspace\Formica-Flow-Latest\test-pdf`
- `antsleap` 环境下验证结果：
  - agent 单元测试通过
  - PDF 筛选处理 8 个 PDF，其中 3 个 0 字节 PDF 被明确记录，5 个可读 PDF 成功提取文本
  - figure 提取对 5 个可读 PDF 成功，生成 30 个候选，整体状态为 `partial`
  - Core-2 治理通过，30 个候选全部进入 `Ambiguous`，没有自动提升
  - 候选导入烟测可写入 30 条 `needs_review` 图片来源追踪
  - 自动标注真实 engine 可调用，但该 PDF 批次保存新标签数为 0，符合“非标准形态图不应自动入库”的预期
  - 训练烟测 1 epoch 通过，未保存正式权重
  - 多模态导出 48 条可信已标注样本，JSONL 校验通过
  - `run_agentic_pipeline.py --execute-ready` 可串起可运行阶段；模型推理仍需要显式 `--allow-model-inference`

### **[2026-04-22] Route Tree v2 路由树 + Blink 训练日志面板 + 高风险专家桶删除 + 定向对话框可用性修补**
> **本次重点：把项目级级联路由真正落成“树形、按项目保存、可审计”的控制界面，同时让 Blink 小专家训练和专家桶清理过程更容易看清楚，也把几个仍然容易误判的界面状态做了定向修补。**

#### **1）项目路由管理现在是真正的树形视图，并且底层改为 `project-v2`**
- `Project Route Management / 项目路由管理` 不再只是平铺 route 的表格感界面，而是改成了 parent -> route -> expert 的树形结构，位置仍在 `Settings -> Model Settings`。
- 项目里的 route manifest 现在使用 `project-v2`，并支持嵌套的 `appointed_expert` 以及 `expert_candidates` 历史/候选记录。
- 旧的扁平 route 记录在载入时仍会做兼容迁移，不会因为格式升级而直接失效。
- 对研究流程的意义是：你现在看到的不只是 `Head -> Mandible` 这条链路存不存在，还能直接看到这个项目里给它指定过谁，候选历史里留下过谁。

#### **2）路由树第三层专家节点现在优先使用项目内已保存的专家历史，运行时扫描到的专家只作为补充候选**
- 路由树第三层现在会先显示项目里已保存的 appointed expert，以及这个项目自己的 candidate/history 记录。
- 运行时从磁盘扫描到的可发现专家仍然会合并显示，但它们现在只是补充候选，不再反过来压过项目自身的路由记忆。
- 当前 route 是否参与级联，也只由项目路由树里的启用/停用状态控制，旧的全局级联总开关继续保持退役状态。
- 对研究流程的意义是：一个项目已经做过的专家指定不会再因为磁盘上后来又出现了别的权重文件，就被界面语义悄悄带偏。

#### **3）Blink 小专家训练现在有可见的 `Training Log / 训练日志` 面板**
- Blink 训练区现在加入了独立的 `Training Log / 训练日志` 面板。
- `TRAIN EXPERT MODEL / 训练专家模型` 运行时，训练器日志会沿着 trainer -> training thread -> UI log console 这条链路显示出来。
- 对研究流程的意义是：训练 Mandible、Eye 这类局部专家时，你终于可以直接在 Blink 里看到过程日志和失败线索，而不是只看到一个按钮卡住或结束。

#### **4）Blink 专家注册表现在支持“子部位专家桶”的高风险删除，并把影响范围先说清楚，再要求二次输入确认**
- 当你选中的不是单个权重文件，而是某个子部位的整个专家桶时，程序会先弹出高风险预览，对话框里会列出：
  - 将删除的桶内文件
  - 当前打开项目里会受影响的 route 分支
- 之后还会再来一次“必须手工输入子部位名称”的 typed confirmation，只有完全一致才会继续永久删除。
- 默认情况下，删除成功后会顺带清理**当前打开项目**里所有匹配的 route 分支，不会去扫描或改动其它项目。
- 对研究流程的意义是：现在删除一个高风险专家桶前，你可以先看清它会影响当前项目的哪些父子链路，也能决定要不要把这些残留 route 一并清掉。

#### **5）这轮定向 UI 修补提升了复选框/单选框选中态可见性，也加强了目标自定义对话框里的 `OK` / `Cancel` 按钮辨识度**
- scientific theme 里的通用 checkbox / radio 选中态现在更清楚，不那么容易在长时间使用时看漏。
- 训练和 Blink 相关的目标自定义对话框里，`OK` / `Cancel` 按钮现在更像真正可点击的动作按钮，辨识度更强。
- 补充同步：全局 `QMessageBox` 的确认类弹窗现在也接入同一套 themed semantic 按钮样式，不只是 `Yes/No`、`OK/Cancel`，连 PDF 提取前那个 `Continue/Cancel` 警告框也一起补齐了。
- 浅色模式下，checkbox / radio 的选中态后来又继续微调过一次：不再只是边框变化，而是恢复了更明确的填充式选中效果，避免看起来像突兀的黑框却又不够好分辨。
- 深色模式下，整套底色从原来偏深蓝黑收回到更中性的深灰系；运行/确认类按钮也从偏亮的天蓝改成了更克制的灰蓝色。
- 对研究流程的意义是：你现在在做删除、覆盖、导出、旧定位器确认、批量运行确认时，不会再遇到“一部分弹窗已经换新样式，另一部分还是旧系统按钮”的割裂感。
- 对研究流程的意义是：长时间做筛选、标注或复核时，浅色模式下“哪个已经选中”会更容易一眼看清；深色模式则不会再有整屏偏蓝、按钮过亮抢眼的感觉。
- 本次没有改动 PDF 提取和 triptych 相关逻辑。

### **[2026-04-21] 训练预检同步 + Locator 动态尺寸对齐 + 项目级路由管理 + 结构化报告**
> **本次重点：把当前实际训练路径、级联路由控制和训练报告整理回“以项目真实保存数据为准”的状态，不再让旧的 manifest 训练说法或全局级联总开关继续误导后续研究使用。**

#### **1）主工作台 `Train Models` 现在依据已保存标注 + 训练预检，不再走文件名/视角门控或 manifest 切分门控**
- 当前主训练入口会直接根据项目里已保存的 polygon 或 box，以及磁盘上真实存在的图像文件决定哪些样本可进入训练。
- `TrainingPreflightDialog` 已替代旧的纯文本预检消息框，现在会明确展示：
  - Locator 和 SAM 可训练图片数量
  - total / train / val 的部位覆盖情况
  - 缺图、不可读图、零标注图、无效标注图的排除清单
- 对研究流程的意义是：训练开始前，你可以先看清楚这次到底会用哪些图，哪些图会被跳过，以及跳过原因。

#### **2）Locator 训练与推理现在使用精确 `(宽, 高)` 尺寸对，而不是默认硬锁 512，同时加入有效部位掩码语义**
- 预检现在会统计 Locator 可训练图片的原生精确尺寸对，并在存在混合分辨率时给出明确 warning。
- 如果同一项目里 Locator 可训练图分辨率混杂，当前训练路径会统一到“可训练样本中最小的精确尺寸层级”，显存不足时也可以按预检给出的更低尺寸对重试。
- Locator 训练现在使用 `valid_parts_mask`，未标注通道不会再被当成真监督去计算假损失或假误差，预检也会分别汇报 Locator / SAM 的 total、train、val 覆盖情况。
- Locator 权重现在会保存真实训练尺寸；如果加载的是没有尺寸元数据的旧 checkpoint，界面会先要求确认，才把它当成兼容旧时代的 `512x512` 模型。
- 对研究流程的意义是：混合尺寸标本图训练更可控，旧模型也不会再悄悄按当前分辨率逻辑硬套进去。

#### **3）级联路由现在变成项目级管理，并移动到 `Settings -> Model Settings`**
- 每个项目现在都会保存自己的 `cascade_routes` 路由树，不再依赖旧的全局级联总开关思路。
- 当你在 Blink 中以父级 -> 子级的上下文进入精修时，程序可以为当前项目登记一条候选 route。
- `Project Route Management / 项目路由管理` 现在允许你为 route 指定专家、启用或停用 route、删除当前项目里的这条 route 记录。
- 单图推理和批量推理现在都会把当前项目的 route manifest 传入推理流程。
- 旧的 `inf_enable_cascade_experts` 已经废弃，并从当前配置清理逻辑中移除。
- 对研究流程的意义是：不同项目的父子部位级联关系终于可以分开审计、分开控制，不会再被一个全局开关混在一起。

#### **4）训练报告的第一阶段细粒度产物已经结构化，报告弹窗也跟着升级**
- 训练报告现在会保存：
  - `report_summary.json`
  - `validation_index.csv`
  - 增强后的 `val_details/` 覆盖图
- `TrainingReportDialog` 现在会读取这些结构化报告文件，不再只依赖一张总览图。
- 本次改动没有触碰 PDF 提取和 triptych 逻辑。
- 对研究流程的意义是：训练结束后，你可以更明确地追踪每张验证图、每张覆盖图以及对应的报告文件，而不是只能靠文件夹里手动猜。

### **[2026-04-10] 4K 精修流畅度修复 + Blink 显式同步化 + 重名素材清理工具**
> **本次重点：解决 4K 标注工作流里“删点后视角回缩”和“高频微调仍被保存/同步打断”的问题，同时补上一套用于清理早期十视图重名 PNG 素材的批量改名脚本。**

#### **1）主工作台现在不会再因为同图删点/拖点而把 4K 视角打回整图**
- 同一张图上的删点、拖点、polygon 精修，现在只更新当前图的 polygon / box / 状态，不再把当前图片重新 `load_image()` 一次。
- 真正切换到另一张图时，仍然会正常重新载入并适配视角。
- 这意味着研究者在 4K 图上放大看细节后，不会再因为一次删点就被打回初始整图视角。

#### **2）Blink 现在回到“进入时同步 + 手动 Sync/Apply 为主”的研究工作流**
- 主工作台现在不再因为同图删点/拖点、单图预测或批量预测结果落到当前图时，就自动把数据推给 Blink。
- 当前更符合研究流程的路径是：
  - 从主工作台 **`Open in Blink Workbench / 在 Blink 工作台中打开`** 时，把当前最新 labels / boxes 显式带入 Blink
  - 之后如果主工作台又有变化，而你真的要 Blink 更新，再手动点 **`Sync from Workbench / 从工作台同步`**
  - Blink 精修后的正式回写仍然通过 **`APPLY TO GLOBAL / 应用到全局`** 完成
- 这让 Blink 在你主工作台连续精修时默认保持闲置，不再白白吃掉同步成本。

#### **3）主工作台高频点编辑现在改成 3 秒延迟自动保存，而不是每一步都整项目写盘**
- 删点、拖点这类高频 polygon 精修，现在会先更新内存里的 `project_data`，并启动单次自动保存定时器。
- 只要研究者继续改点，定时器就会后移，不会每一步都立刻 `save_project()`。
- 当前默认延迟已经调到：
  - **3000 ms（3 秒）**
- 但以下边界仍然会立即落盘：
  - 切换图片
  - 新建/打开项目
  - 导入/删除图片
  - 导出
  - 训练
  - 手动保存
  - 关闭程序
- 对研究流程的意义是：连续微调更顺，但换图、导出、训练前仍然会安全保存。

#### **4）补了一套清理早期十视图重名 PNG 素材的批量改名脚本**
- 仓库现在新增了工具脚本：
  - `tools/rename_pngs_with_folder_prefix.py`
- 它会把旧批次里每个标本子文件夹内的 PNG 改成：
  - **`文件夹编号_原视角文件名`**
  - 例如：`01-01/front.png -> 01-01_front.png`
- 这套脚本已经用于清理早期 `specimens` 目录以及 4K/8K 备份目录中的同名十视图素材；素材重名清理后，左侧列表里的批量删除行为已经恢复正常。

### **[2026-04-02] 正式版前端对齐 + 主题系统并入 + 前后端复核通过**
> **本次重点：把前端测试分支中已经验证过的浅色 / 深色主题优化，正式并入 LBJ-workspace 这份更稳定的正式版，同时保留并复核它原有更成熟的 Blink / 项目状态 / 模型切换逻辑。**

#### **1）正式版现在不再只是旧的深色抛光，而是正式接入了新的双主题工作台体系**
- `AntSleap/ui/style.py` 已升级为统一主题源，正式支持：
  - `dark`
  - `light`
- 主窗口设置菜单现在可以直接切换主题。
- 主工作台、PDF 面板、Blink 工作台现在共用同一套主题语义，不再出现：
  - 一部分区域已经是新面板体系
  - 另一部分按钮 / 输入框还停留在旧色板

#### **2）主题切换现在会真正贯穿研究者的完整操作路径，而不只是改主窗口外壳**
- `AntSleap/main.py` 现在会把主题切换继续传递到实际工作控件，包括：
  - 顶部 `Export Dataset`、`Import & Crop`、`Open in Blink Workbench`
  - 左侧 `+ Add Images`
  - 标注工作台 AI 控制按钮
  - `PdfProcessingWidget`
  - `BlinkLabWidget`
- 这修掉了旧状态下“切主题后局部按钮仍残留上一套配色”的问题，尤其是中性按钮不会再在明暗模式之间串色。

#### **3）Blink 和 PDF 子工作台也被拉进同一套视觉体系，但没有改动它们的行为逻辑**
- `AntSleap/ui/blink_lab.py` 现在已经支持正式版主题刷新：
  - 训练轮次 / 批次设置在浅色模式下可读性正常
  - 行为按钮会跟随主题走正确语义色
  - Blink 训练设置区域不再像散落控件，而是完整的一块信息面板
- `AntSleap/ui/pdf_processing_widget.py` 也补上了主题刷新：
  - 操作按钮会跟随主题变化
  - 日志区会同步切换到当前主题的底色和边框
  - 文献处理工作区不再掉回旧配色

#### **4）并入前端后，正式版原有后端 / 工作流逻辑已经复核，仍保持合理**
- 这次专门重新核查并确认保留了正式版原有的稳定逻辑，包括：
  - 存在项目数据中的 Blink 父级 / 上下文 ROI 记忆 (`blink_context_roi_parents`)
  - 从工作台显式建立 Blink 会话的进入逻辑
  - 删除 locator / segmenter 后运行态与下拉框状态同步回落
  - 项目保存 / 读取时对 Blink 上下文记忆的持久化
- 也就是说，这次是：
  - **把前端优化对齐进正式版**
  - 不是去改写正式版已经更稳定的后端行为

### **[2026-03-31] 研究者导向界面细化 + Blink 上下文记忆 + 文献筛选文案澄清**
> **本次重点：把工作台继续收紧为更适合长时间使用的研究界面，把 Blink 入口从“硬编码父级关系”改成“研究者自己选择并按项目记忆”，并清理几个已经不再一眼能懂的前端控件表达。**

#### **1）主工作台进一步收口为更平静、更适合长时间使用的图像优先界面**
- 共享深色主题和面板层级继续统一了以下三个主界面：
  - `PDF Processing`
  - `Labeling Workbench`
  - `Blink Workbench`
- 标注工作台现在更像真正的标注工作面，而不是一堆功能块的拼接：
  - 图像 / 画布仍然是最强视觉主角
  - 右侧信息区的分组更平静
  - 日志、元数据、AI 控制区更像三个明确表面
- 在不改变工作流的前提下，长时间使用舒适度也做了收口：
  - 主工作台和 Blink 的分隔条更容易拖拽
  - 亮度 / 对比度滑条更容易细调
  - 单选框、复选框、树控件、右侧 inspector 表面风格更加统一
  - Blink 遮罩强度降低，不再像之前那样过度压黑

#### **2）Blink 入口不再依赖硬编码部位关系，而是按项目记住研究者自己选过的父级 / 上下文 ROI**
- 之前临时存在的“硬编码父级偏好”路径已经从 Blink 默认进入逻辑中移除。
- 现在 Blink 入口遵守更严格、也更符合研究判断的规则：
  - 如果某个目标部位还没有记住过父级 / 上下文关系，弹窗**不会**替你偷偷猜一个
  - 当研究者第一次明确为某个目标部位选定父级 / 上下文 ROI 后，这个关系会被记到当前项目里
  - 之后同一项目里再次进入相同目标部位的 Blink，会自动复用这份项目内记忆
- 这份记忆保存在项目数据中，而不是全局软件设置里，所以一个项目的部位判断不会污染另一个项目。
- 如果研究者后来改成直接用目标部位本身作为进入 ROI，程序会清掉这个部位原先记住的父级关系，而不是永久强行套用旧判断。

#### **3）工作台里的模型选择控件现在更清楚、更安全，也不再排版漂移**
- `Locator` 和 `Segmenter` 右侧的危险按钮现在终于是“看得懂、状态正确”的：
  - 英文界面显示 `Del`
  - 中文界面显示 `删除`
  - 两者都补上了明确 tooltip，说明会从磁盘删除当前选中的模型文件
  - 当当前选择本来就不可删除时，按钮会自动禁用
- Locator 删除路径已修正为真正的 `locator_<timestamp>.pth`，不再去删旧的错误路径形式。
- 删除当前正在使用的 locator / segmenter 后，运行态现在会同步回到下拉框显示的真实状态：
  - segmenter 会回到 `Base SAM`
  - 当没有训练 locator 剩下时，locator 会回到基础 / 未训练状态
- 英文界面里的 `Locator / Segmenter / Del` 这两行，现在已改成共享列宽的对齐网格，不再因为标签长度和默认内容不同而视觉上一长一短。

#### **4）PDF Screener 里的 V2 运行目录选项，现在直接把含义说出来了**
- 原来那个抽象的 `Isolate V2 Runs / 隔离 V2 运行` 复选框，已经改成“直接说明作用”的写法：
  - 英文：`V2: separate folder per run`
  - 中文：`V2：每次运行独立文件夹`
- 同时还补上了明确 tooltip，直接说明这个选项做的事：
  - 每次 V2 运行都会在 `Output Dir` 下使用独立子文件夹
  - 这样不同运行结果不会混在一起
- 运行日志里的同名提示也同步成同一套语义，避免界面和日志对同一个选项说两套不同的话。

### **[2026-03-23] 主定位器范围拆分 + Blink 草稿辅助工作流 + 启动窗口安全化**
> **本次重点：把主定位器的宏观范围和完整项目 taxonomy 正式拆开，让 Blink 真正变成“先起草、再精修”的局部工作台，并修复主窗口启动时可能部分跑出屏幕外的问题。**

#### **1）主定位器现在默认只做 3 个大部位，但系统不再被硬锁死**
- 新项目现在默认把 `taxonomy` 和 `locator_scope` 都设为：
  - `Head`
  - `Mesosoma`
  - `Gaster`
- 这意味着主定位器默认回到“大部位粗定位”职责，不再默认把 `Mandible`、`Eye` 这类小部位也一起塞进同一个热图头里学习。
- 如果之后再添加小部位，扩展的是**项目完整 taxonomy**，不会再悄悄扩大**主定位器范围**。
- 旧项目兼容逻辑也保留了：
  - 如果旧 JSON 里没有 `locator_scope`，程序仍会把旧 taxonomy 当成 locator scope，避免历史项目被静默改语义。

#### **2）Blink 轨迹现在会记住父级上下文，小专家训练也真正回到父级 crop 里**
- Blink 轨迹现在除了 frame 序列，还会保存 `parent_context`，包括：
  - `parent_part`
  - `parent_box`
  - `source`
- Blink 小专家训练现在会利用这层父级上下文，在父级 crop 上训练，而不是默默退回整图语义。
- 针对当前蚂蚁工作流，还新增了默认级联路由：
  - `Head -> Mandible`
  - `Head -> Eye`
- 这样系统终于更接近预期的宏观→微观路径：
  - 先找大部位
  - 再由子部位专家继续细化

#### **3）Blink 现在已经不只是“手工画 polygon”，而是一个真正的草稿 + 精修工作台**
- Blink 现在支持 **`AUTO-ANNOTATE DRAFT / 自动标注草稿`**：
  - 当前 active expert 先在 session ROI 内给出局部框
  - 基础 SAM 再把这个框转成 draft polygon
  - 研究者直接在此基础上精修
- Blink 现在也支持 **`Draw Box (For SAM Draft) / 绘制框（SAM 草稿）`**：
  - 研究者自己画一个临时提示框
  - 基础 SAM 立刻据此生成 draft polygon
- 这些提示框被明确设计成**临时草稿提示**，不会被当成后面 shrink 用的松散框。
- 原来的 Blink 训练路径仍保持不变：
  - 先精修 polygon
  - 再画一个松散 shrink 框
  - 再执行 `EXECUTE AUTO-SHRINK / 执行自动收缩`

#### **4）面向研究者的提示与安全性进一步补齐**
- Blink 入口弹窗现在明确解释：
  - **Target Part / 目标部位** = 要精修的子部位
  - **Entry ROI / 进入 ROI** = Blink 要放大的父级/上下文区域
  - 还会直接举 `Eye -> Head` 的例子
- Blink 控制区状态文字现在支持自动换行，不会再把长提示/长报错截成半句。
- 主窗口启动现在会按屏幕可用区域安全定位：
  - 理想大小仍是 `1600x1000`
  - 屏幕够大时会自动居中
  - 屏幕放不下时会先收进可见区域，再居中显示

### **[2026-03-20] 已接受的 UI 收尾：按钮语义统一 + 最终中英文字体方案落定**
> **本次重点：把按钮颜色从“每块面板自己强调”收敛为稳定的语义角色，明确哪些动作属于正式回写、运行、工具、停止、危险操作，并确定当前 Windows Qt 版本下最终采用的中英混排字体方案。**

#### **1）按钮颜色现在按语义统一，不再到处各写一套强调色**
- 共享语义化按钮角色现已集中到 `AntSleap/ui/style.py`：
  - `commit`
  - `run`
  - `neutral`
  - `destructive`
  - `stop`
- 非破坏性的保存 / 回写动作，不再因为“看起来重要”就误用危险风格。
- 真正的删除 / 清空 / 移除动作继续保留危险语义，而停止 / 取消类动作不再看起来像硬删除。

#### **2）当前前端里几个关键按钮的语义基线已经锁定**
- `AntSleap/ui/cropper.py`：**`Save & Add to Project / 保存并加入项目`** 现在明确是正常保存/提交动作，不再像危险操作。
- `AntSleap/ui/blink_lab.py`：**`APPLY TO GLOBAL / 应用到全局`** 现在明确表示 Blink 中的正式项目写回动作，并使用提交语义。
- `EXECUTE AUTO-SHRINK / 执行自动收缩`、训练/启动类动作继续保持运行语义。
- `BLINK SWITCH`、同步、刷新、浏览、打开等动作统一视为中性工具/导航操作。

#### **3）同日试验后，当前最终字体方案已经确定**
- 拉丁文字界面优先使用 **`Cambria`**。
- 中文界面优先使用 **`Microsoft YaHei UI` / `Microsoft YaHei`**。
- 中文衬线字体仍保留在后备链路里，但不再作为默认优先项，因为宋体/SimSun 方向在长时间界面阅读中显得更锐利、更生硬。
- 输入区 / 日志区等等宽场景继续保持 **`Consolas` / `Courier New`**。

#### **4）Windows 启动时现在会先注册所需字体，再显示主界面**
- 当前 Windows Qt 启动路径会在创建 `MainWindow()` 之前预注册所需字体文件。
- 这是当前用于避免中英混排界面出现 tofu / 缺字方块问题的主动修复措施。

### **[2026-03-19] Blink 工作台入口打通 + 中文界面清补 + 搬盘路径兜底**
> **本次重点：把 Blink 真正接到标注工作台后面，明确每个 Blink 按钮到底保存什么内容，补齐主要中文界面缺口，并在 `Formica-Flow_output` 搬盘后仍尽量保持项目可用。**

#### **1）Blink 现在通过工作台显式进入，不再靠“选图后自己猜”**
- 标注工作台新增 **`Open in Blink Workbench / 在 Blink 工作台中打开`** 入口，不再只是被动同步当前图片后默认全图显示。
- 从工作台进入 Blink 时，会先弹出一个小会话对话框，让操作者明确选择：
  - **目标部位**（这次真正要精修谁）
  - **进入 ROI**（通过哪个手工框或自动框进入局部视图）
- 这样大部位定位流程和小部位精修流程终于接上了，但原有热度图定位器主链没有被改掉。

#### **2）Blink 里几个关键按钮的语义现在更清楚了**
- **`Sync from Workbench / 从工作台同步`**：把工作台标注重新载入 Blink，但如果当前 Blink 会话有未应用的本地修改，会先保护并要求你明确决定是否放弃。
- **`BLINK SWITCH`**：只切换局部观察模式（`NORMAL / INSIDE / OUTSIDE`），本身不保存标注。
- **`EXECUTE AUTO-SHRINK / 执行自动收缩`**：立即把当前部位的收缩轨迹保存进项目 `trajectories`，这部分是 Blink 训练数据。
- **`APPLY TO GLOBAL / 应用到全局`**：把这次精修后的结果正式写回主项目，但只回写当前目标部位，不会把局部视图里其它可见上下文一起覆盖。
- **`TRAIN EXPERT MODEL / 训练专家模型`**：训练当前部位对应的 Blink 微观专家，只会读取当前项目里这个部位的 trajectory 样本。

#### **3）Blink 会话行为现在更符合“粗到细”的真实工作流**
- 从工作台进入 Blink 时，会优先按你选定的 ROI 聚焦，而不是继续默认整张图。
- 局部视图里可以保留必要的上下文框，但真正可编辑的多边形工作会收紧到当前目标部位。
- 如果 Blink 里已经有未应用的本地修改，再切图、切会话或强制同步时，程序会先要求你确认，而不是悄悄覆盖。

#### **4）研究者常用界面的中文缺口做了集中清补**
- 主工作台弹窗、Blink 进入对话框、Blink 控制区与状态提示、裁剪器流程文字、PDF 页运行参数区，现在中文覆盖明显更完整了。
- 导出格式虽然能显示成中文，但底层导出类型标识仍保持稳定，不会因为翻译影响实际导出逻辑。

#### **5）搬盘后的图片路径现在有兜底，但坏 JSON 仍然不是一回事**
- `ProjectManager` 现在可以在检测到旧项目仍指向 `Formica-Flow_output` 时，把路径兜底映射到 `C:\savedata\Formica-Flow_output`，前提是新位置的文件确实存在。
- 这个能力只是在解决“图片库搬家后找不到原图”的问题。
- 它**不等于** GUI 能自动修复损坏的项目 JSON；如果 JSON 语法本身坏了，仍然需要先做人工/外部修复。

### **[2026-03-09] v3.11 三视图提取器 V2.0 + 真/假多模态防误判护栏（当前版本）**
> **本次重点：把 PDF 图片提取从“原始图片对象”重构为“整张三视图 figure”，引入与 `gpt-5.4` 兼容的批量多模态复核，并在前端把 mock/default 降级显式提示给用户。**

#### **1）提取单位改为整张 figure，不再直接围绕原始嵌图对象工作**
- `EnhancedPDFExtractionSystem` 已重构为 **figure-region candidate** 流程，不再直接把 PDF 原始 image object 当最终候选单位。
- 候选发现现在会同时利用页面 image rect 与 drawing/vector rect，并在必要时聚成一个完整 figure 区域。
- 当前接受的核心单位是 **整张蚂蚁三视图 figure**；若主体仍是三视图，附带地图、比例尺、少量 inset 也允许保留。

#### **2）落库单位升级为 figure 级，并增加分层文本证据**
- 提取数据库语义已切到 figure 级：
  - `pdf_files`
  - `figure_records`
  - `figure_evidence`
  - `extraction_stats`
- 文本证据按三层保存：
  - `figure_local`
  - `species_core`
  - `species_extended`
- 与单次提取运行相关的新产物现在落到 `<db_stem>_v2_artifacts/` 下，包括：
  - `figure_images/`
  - `review_batches/`
  - `batch_raw_responses/`

#### **3）多模态复核改为批量模式，并与 `gpt-5.4` 配置路径对齐**
- `MultimodalValidator` 现在支持 **一批多个 figure 候选** 一次送审，不再是“一张图一次请求”。
- 提取器侧多模态调用改为 OpenAI 兼容路径，同时支持 `responses` 与 `chat_completions`。
- 对 `gmn.chuangzuoli.com + gpt-5.4` 的协议选择与模型规范化逻辑，现已与文献分类器保持同一兼容思路。
- 每个批次会保留批次清单和原始回包，便于后续审计与排查。

#### **4）通过条件加入硬门槛，mock/default 不再悄悄当真**
- figure 只有在以下条件全部满足时才会进入 accepted：
  - 真实多模态复核确实跑了
  - 置信度达到阈值
  - 没有被标成 `comparison_figure`
  - 没有被标成 `multiple_species`
  - 三视图核心视角齐全：`lateral + dorsal + head_frontal`
- mock/default review 现在不会再自动 accepted，也不会自动终裁 reject。
- 非真实复核结果会统一进入 **Review**，并带 `mock_review_only` 等原因码。

#### **5）前端已增加针对 mock/default 的显式提醒**
- 提取任务启动时，如果真实多模态未配置好、被关闭或初始化失败，主日志会立即给出 warning。
- 单篇 PDF 处理完成后，如果其中有 figure 走了 mock/default review，主日志会明确告诉用户“这些结果进入 Review，不是真正 acceptance”。
- 点击 **Start Extraction Pipeline** 前，如当前配置会退回到 mock/default review，前端会先弹出确认框，用户确认后才会继续。
- 数据库查看器与候选导出链路现在都能看到 figure 级状态，如 `review_status`、`multimodal_review_mode`、`species_candidate`。

#### **6）在初版 V2.0 之后又继续收紧了截图边界**
- 提取器现在把内部用于找文字证据的 `context_bbox` 与真正用于保存 PNG 的 `clip_bbox` 分开处理。
- 保存图像前会进一步收紧边缘，把明显贴着外边缘的 caption / 邻近正文尽量挡在裁剪图之外。
- 我们已用 `11.27-newspecies-pdf/llm-check` 里的真实 PDF 做了抽样验证，外部正文/图题混入情况明显下降，而整张三视图主体基本仍能保持完整可用。
- 当前保留了一份可供人工验收的验证产物：`.tmp_validation/real_triptych_crop_check_keep/`。

#### **7）同日还同步了文献筛选端的收尾修正**
- 文献筛选 `pdf_extract_timeout_seconds` 默认值已从 `180` 秒改为 `30` 秒。
- V2 筛选结果现在会记录 `extract_source`（`text_layer` / `ocr` / `failed`），并写入队列、结果和统计摘要。
- 中断续跑的易用性也已增强：支持恢复中断运行参数，并在无法续跑时给出更明确的原因说明。

---

### **[2026-03-07] v3.10 文献筛选 V2 重构 + 大规模运行加固（当前版本）**
> **本次重点：将“规则前置筛选”重构为“CSV先行 + 全量LLM校验”，并进一步把 3 万篇级别运行需要的续跑、产物治理与诊断能力补齐。**

#### **1）默认筛选流程升级为 V2（CSV-first + 全量LLM）**
- `LLMScreenPDFClassifier` 默认 `processing_mode = v2`。
- 每篇 PDF 先提取前 30 行并写入 `master_queue.csv`；成功提取到文本的行再按批进入 LLM 校验，文本缺失的行会直接进入人工复核。
- 每条文献引入稳定编号（`RID000001`）用于结果映射，降低批量返回错配风险。

#### **2）Legacy 旧流程保留为可回退模式**
- 原规则优先流程未删除，作为 `legacy` 模式保留。
- `batch_classify()` 现在明确按模式分发到 `v2` 或 `legacy`。

#### **3）V2 新增标准化产物**
- 新产物现在按运行目录归类；默认在开启 `Isolate V2 Runs` 时落到 `v2_runs/run_*/`：
  - `resume_state/master_queue.csv`
  - `resume_state/csv_batches/*.csv`
  - `resume_state/run_index.json`
  - `core_results/master_results.csv`
  - `core_results/selected_record_ids.csv`
  - `core_results/move_manifest.csv`
  - `core_results/llm_enhanced_classification_details.csv`
  - `debug_evidence/batch_raw_responses/*.txt`
- 输出根目录额外保留 `v2_active_run.json`，用于中断续跑协调。
- 最终通过文献复制到 `core_results/final_new_species_reports/`，不确定样本进入 `core_results/manual_review_uncertain/`。

#### **4）前端可控性与防误操作增强**
- 文献筛选新增模式切换：`V2（CSV全量LLM）` 与 `Legacy（规则预筛）`。
- 逻辑方案下拉改为“按模式过滤”，避免“旧方案误跑新逻辑”。
- 高级逻辑弹窗中，关键词在 V2 语义改为“辅助词库”，Legacy 下才作为硬规则。

#### **5）API 设置持久化与协议选择上线**
- 增加 `保存API设置` 和可选 `记住API密钥`。
- 增加 `API协议` 选择（`Auto`、`Chat Completions`、`Responses API`），并写入运行时设置文件。

#### **6）经销商接口兼容与稳定性加固**
- 新增 `responses` / `chat.completions` 协议适配层与自动选择逻辑。
- 针对 `gmn.chuangzuoli.com` 增加模型名与地址规范化，并支持直连 HTTP `/responses` 通道。
- 增加关键风控机制：
  - 批量输出完整性约束（防漏条/重复）
  - 截断检测（`length` / `incomplete`）
  - `401/403/404/422` 不可重试快速失败
  - 错误日志包含 `protocol/model/base_url` 关键信息
  - 分阶段进度条，避免任务未结束就显示 100%

#### **7）大规模 V2 运行支持“断点续跑”**
- 中断后的 V2 运行现在可以直接在原 run 目录上恢复，不必从头开始。
- 续跑前会校验：源目录、运行时签名、PDF 清单签名，以及 `master_queue.csv` 是否完整可复用。
- 部分运行不再错误生成 `selected_record_ids.csv`、`move_manifest.csv` 这类“看起来已完成”的产物。
- 非隔离模式下，启动前会自动清理旧 V2 产物，避免污染新任务。

#### **8）`gpt-5.4` 首测默认参数与安全旋钮已同步**
- 默认文献筛选模型改为 `gpt-5.4`。
- 默认 V2 首测参数调整为：
  - `lines_per_pdf = 30`
  - `csv_batch_size = 80`
  - `csv_batch_fallback_size = 40`
  - `batch_char_budget = 100000`
  - `max_text_chars_per_file = 1600`
  - `llm_batch_max_tokens = 12000`
  - `llm_request_timeout_seconds = 240`
- PDF 前端新增运行安全参数：
  - `Prompt Char Budget`
  - `Text Chars/File`
  - `LLM Max Tokens`
  - `LLM Timeout(s)`
  - `Auto Split Failed Batches`
  - `Resume Interrupted Runs`
  - `Isolate V2 Runs`

#### **9）OCR 与坏 PDF 诊断能力增强**
- 在 OCR 前新增 PDF 预检查：
  - 文件不存在
  - 空文件 / 空内容流
  - 非法 PDF 头
  - 缺少 EOF 的不完整 PDF
  - `/Root`、xref、trailer 等结构损坏
- 这类文件现在会落成明确问题码，如：
  - `pdf_empty`
  - `pdf_invalid_header`
  - `pdf_incomplete`
  - `pdf_invalid_structure`
  - `pdf_unreadable`
- 因此日志里的“OCR失败”现在能和“源 PDF 已损坏/不完整”区分开来。

#### **10）原始回包与批次 CSV 体积同步瘦身**
- 批量 LLM 成功返回后的完整原始回包，改为单独保存到 `debug_evidence/batch_raw_responses/<batch_id>.txt`。
- 批量成功返回时，CSV 中的 `llm_raw` 现在保存的是文件引用，而不是把整段原始响应复制到每一行。
- `csv_batches/*.csv` 也已改成轻量字段，只保留续跑/审计必须的数据，不再重复存 `text_preview` 等大字段。

#### **11）单篇 PDF 防卡死 + 阶段 1 队列断点落盘**
- 每篇 PDF 的文本层/OCR 提取现在都放到受保护的子进程里执行，并受 `pdf_extract_timeout_seconds`（默认 `180` 秒）限制，因此单个坏 PDF 不会再把整批分类无限卡住。
- 停止按钮仍然是协作式停止，但现在最多只需要等“当前这篇 PDF 正常结束或触发超时”；`v2` 和 `legacy` 两种模式共用同一层防护。
- `resume_state/master_queue.csv` 现在会在阶段 1 按 PDF 逐条增量写入；V2 续跑也接受“前缀完整”的部分队列，因此中途中断后会从下一篇继续，而不是把前面已经做完的行全部丢掉重来。
- 坏文件或超时文件会以 `text_missing` + 明确问题码的形式落盘，并进入后续人工复核路径，而不是悄悄堵住整个批次。

---

### **[2026-03-06] v3.9 Core-2 治理流水线 + 候选池使用说明（当前版本）**
> **本次重点：让训练与评估可复现、可验收，并明确 PDF 候选数据在“当前前端”中的实际审核方式。**

#### **1）Core-2 治理链路已完整落地**
- 新增 `AntSleap/core/governance/` 与 `tools/governance/`，覆盖：
  - 视角合同校验与迁移
  - 确定性切分与泄漏检查
  - 分视角评估、红线判定、低样本保护
  - 头视角监控（非阻塞）
  - 候选导出、风险抽样、分流、去重/幂等
  - 升级触发器、自动验收套件、一键编排
- 治理策略统一由 `AntSleap/config/view_policy_core2.json` 管理。

#### **2）训练切分逻辑已变更（重要）**
- `main.py` 的训练流程默认改为 **清单驱动（manifest-first）**，不再默认运行时随机切分。
- 新配置项：
  - `train_split_manifest_path`
  - `train_core2_manifest_path`
  - `train_allow_random_fallback`（默认 `False`）
- 若清单缺失且不允许随机兜底，训练会明确报错中止，而不是悄悄随机化。

#### **3）当前“候选池”是报告/产物层，不是新前端页面**
- 前端仍然是原有按钮：
  - `Start Extraction Pipeline`
  - `Browse Database`
  - `Export Raw JSONL`
- “候选池”目前体现为治理产物文件（用于审核与分流），不是可点击审批的新 Tab。
- 关键产物示例：
  - `artifacts/core2/pdf_candidates_raw.json`
  - `artifacts/core2/review_sampling_report.json`
  - `artifacts/core2/routing_decisions.json`

#### **4）启动稳定性修复**
- 修复 `core.pdf_processor` 导入异常：`AntSleap/ui/pdf_processing_widget.py` 增加导入兜底加载。

#### **5）文档与可执行检查已对齐**
- 新增运行手册：`docs/core2_governance_runbook.md`
- 新增文档-策略一致性检查：`tools/governance/check_docs_policy_sync.py`

---

### **[2026-03-05] v3.8 安全收敛与文档同步（本次会话收尾）**
> **本次重点：收紧 BLINK 数据契约、将级联专家切换为默认安全模式，并明确下一阶段优化方向。**

#### **1）BLINK 坐标/数据契约加固**
- `CoordinateMapper` 增加统一工具：框坐标清洗、边界裁剪、尺寸映射、归一化，训练与推理统一用同一套“坐标尺子”。
- 轨迹帧新增显式字段：`coord_frame` 与 `target_box`，避免局部/全局坐标混淆。
- `ProjectManager` 在保存轨迹时会自动清洗非法帧；删除部位标签时会同步删除对应轨迹，防止旧数据污染训练。

#### **2）BLINK 训练升级（从“终点监督”走向“过程监督”）**
- `BlinkTrajectoryDataset` 现在输出双视角样本（`inside_image` / `outside_image`）以及双目标（`target_step` / `target_final`）。
- `BlinkExpertTrainer` 采用混合损失：终点质量 + 过程推进 + 双视角一致性，训练信号更贴近白皮书思想。
- 专家权重路径统一到 `AntSleap/weights/experts/<Part>/`，减少路径漂移问题。

#### **3）推理输出协议重构**
- `predict_full_pipeline` 统一返回结构化结果：
  - `polygons`
  - `auto_boxes`
  - `scores`
  - `meta`
- 清除了流水线中的重复 SAM 调用。
- 单图与批量写回统一走 `main.py` 同一解析函数；同时保留旧 `_BOX` 协议兼容。

#### **4）级联专家进入“默认关闭 + 双门禁”模式**
- 新配置项：`inf_enable_cascade_experts`（默认 `False`）。
- 设置面板新增实验开关：**Enable Cascade Experts**。
- 即使手动打开开关，也必须满足路由合同才允许覆盖：
  - 文件：`AntSleap/weights/experts/cascade_routes.json`
  - 条件：`approved=true` 且存在有效 `routes`。
- 这保证了解剖学级联关系由领域专家定义，不由系统隐式假设。

#### **5）Blink 工作台训练线程化**
- 增加 `BlinkTrainingThread`，训练专家模型改为后台线程，避免 UI 卡死。

#### **6）当前讨论后的临时策略（已记录）**
- 近期优化方向暂定：宏观定位器先聚焦 **侧视图 + 俯视图**，`head-view` 先做筛选分流，不直接并入主训练流。
- 方向增强建议“保守实施”：小角度、标签一致的增强优先，避免不合理旋转/翻转引入伪噪声。
- PDF 筛选提取流程与标注工作台尚未正式打通到统一数据入口策略，此项已纳入后续计划。

---

### **[2026-03-03] v3.7 眨眼迭代算法 (BLINK) 的诞生：从概念白皮书到主动学习工厂**
> **“不仅是一个工具，更是像科学家一样理解解剖学的 AI。”**

本次更新标志着 **眨眼迭代精修 (BLINK)** 算法的正式落地。研发过程经历了四个极具挑战性的进化阶段，旨在彻底解决显微形态学中的“分辨率-精度悖论”。

#### **第一阶段：搭建物理桥梁（基础设施）**
*   **痛点**：在 4K 级别的标本大图中，微小器官（如大颚齿序）因巨大的分辨率损失在 AI 视角下几乎处于“隐身”状态。
*   **解决方案**：我们构建了 **BLINK 专家实验室** —— 一个独立的高清标注沙盒。
    *   **动态缩放引擎 (Zoom-in Engine)**：实现了递归裁剪系统，能自动从全图中锁定父级器官（如头部），并以双三次插值（Bicubic）算法无损放大至 224px 的标准专家视窗。
    *   **坐标无损重投影**：通过 `CoordinateMapper` 仿射变换矩阵，打通了局部高清图与 4K 原始大图之间的“物理虫洞”。确保实验室中的任何微观操作都能零误差地反向映射回真实地理坐标。

#### **第二阶段：算法逻辑纠偏（收缩策略的进化）**
*   **初始原型（盲目探测）**：最初我们尝试让 AI 仅根据 SAM 掩码的崩溃临界点进行自主收缩。
*   **战略转折（人类定调）**：在实测中我们发现，缺乏“科研底线”的机器容易发生边界幻觉。我们果断回归《眨眼算法白皮书》初衷，确立了**“倒果为因”**的教学逻辑。
*   **最终实现**：
    *   由人类专家手动精修出“黄金多边形”（确立真理底线）。
    *   算法自动计算从松散大框到黄金靶心的 **20 帧渐进式收缩轨迹**。
    *   这为 AI 批量生产了完美的“动态教材”，教导模型如何从不确定的模糊方位一步步逼近解剖学极限。
    *   引入 **3% 的呼吸间距 (Padding Safety)**，防止框体死死贴住边缘导致 SAM 失去上下文参考，确保了分割的鲁棒性。

#### **第三阶段：认知能力飞跃（Transformer 与 眨眼博弈）**
*   **CNN 还是 Transformer？**：我们深入探讨了 CNN 在全局视野上的局限性 —— 它擅长纹理，但在“遮挡博弈”中会变成瞎子。
*   **Vision Transformer (ViT-B/16) 落地**：依托双 RTX 3090 的算力，我们将专家的大脑升级为拥有 8600 万参数的 ViT 架构。
*   **“眨眼博弈” (Inside/Outside 训练)**：这是算法的灵魂。在训练中，系统会随机切换视角：
    *   **Inside-View (看内部)**：遮蔽框外一切，强迫 AI 学习微观纹理（齿序、刚毛）。
    *   **Outside-View (看全局)**：遮蔽部位本身，强迫 AI 学习**解剖学拓扑逻辑** —— 必须通过头壳弧度、触角位置“推断”出被遮挡部位的精确边界。
    *   **成果**：这种双视角一致性强制 AI 理解“解剖学真理”而非死记硬背像素，实现了真正的**跨物种通用性**。

#### **第四阶段：级联工厂落成（生产集成）**
*   **递归调度**：编写 `CascadingManager` 打通了 UNet (宏观定位) 与 ViT (微观专家) 的接力。
*   **专家拦截机制**：自动标注流程中加入了“智能路由”。一旦检测到某个部位已有训练好的专家模型，系统将拦截原有的粗糙输出，执行自动对焦、专家精修，最后由 SAM 生成完美掩码。
*   **模型资产管理**：引入树状版本管理系统，支持按时间戳管理历史版本归档，使整个系统进化为可工业化生产的“模型铸造厂”。

### **[2026-03-02] v3.6 文献筛选通用化与多方案管理 (Generalization Update)**
> **本次更新重点：打破物种限制，让科研人员自主定义 AI 筛选逻辑。**

- **多方案管理系统 (Screener Profile System)**:
    - **自定义方案**: 用户现在可以为不同的研究领域（如：植物、甲虫、鱼类）创建独立的筛选方案。
    - **持久化存储**: 所有方案以 JSON 格式保存在 `screener_configs/` 目录下，支持“另存为”、“覆盖”和“删除”操作。
    - **快速切换**: 主界面新增下拉选择框，支持在不同逻辑间一键切换。
- **全参数开放配置**:
    - **关键词自定义**: 开放了核心关键词、支持词、识别词、强排除词、弱排除词及生物干扰排除词的编辑。
    - **提示词自定义 (Prompt Customization)**: 允许用户修改 LLM 复查时的专家身份、判断标准及回复格式。
- **UI/UX 深度优化**:
    - **高级逻辑设置**: 新增专用配置对话框，预置“默认蚂蚁逻辑”作为参考。
    - **超大提示词框**: 优化了 Prompt 编辑体验，提供 350px 高度的编辑区域。
    - **实时验证日志**: 日志框现在会明确显示当前任务正在使用的方案名称及加载的关键词摘要，确保“所见即所得”。
- **底层算法去中心化**:
    - 彻底移除了代码中硬编码的“蚂蚁”术语。评分引擎现在完全基于用户定义的 `taxonomic_group_keywords` 动态运行。

### **[2026-01-06] v3.5 显式框体监督 ("真值"升级)**
> **本次更新重点：利用人工核验的包围框最大化训练精度。**

- **显式框体监督 (Explicit Box Supervision)**:
    - **新逻辑**: 当使用“框选 (Box Prompt)”工具时，系统现在会持久化存储用户绘制的精确坐标（存为 `boxes`）。
    - **训练影响**: 定位器的 **WH 回归头** 现在会优先使用这些手动框作为“真值”进行训练。
    - **导出影响**: **COCO** 和 **YOLO** 导出功能现在同样会优先使用手动框作为 `bbox` 字段，确保数据集完美体现人工核验的边界。
- **VLM 专用双视图导出 (Dual-View Export)**:
    - **架构**: 多模态导出功能现在生成 **双视图** 数据集（全局概览图 + 高清局部切片）。
    - **优化**: 数据包含空间坐标 (`bbox_global`) 将切片关联回全图。专门为 **Qwen2-VL**、**GPT-4V** 等新一代大模型优化。
- **可视化调试系统**:
    - **绿色虚线框**: 代表 **人工真值 (Manual Ground Truth)**。用于训练。
    - **橙色虚线框**: 代表 **AI 预测值 (AI Predictions)**。用于校验。
- **数据完整性与稳定性**:
    - **自动修复 (Auto-Repair)**: 自动检测并修复丢失的图片索引条目，彻底解决了“无法保存标注”的问题。
    - **坐标清洗**: 所有输入坐标在保存前经过严格清洗和截断，防止边缘情况导致系统崩溃。
    - **UI 逻辑修复**:
        - **智能排序**: 列表现在按状态分区显示——**已标注**图片始终保持在上方（绿色），**未标注**图片自动下沉至底部（灰色）。这让用户能一眼看清剩余工作量。
        - **人工覆盖自动**: 手动更新框体时会自动清除该部位陈旧的 AI 标注框，彻底解决“双重框”视觉重影问题。
        - **UI 焦点锁定**: 修复了“列表乱跳”问题，文件列表在刷新后保持选中状态。

### **[2026-01-05] v3.4 架构解耦与推理优化**
> **本次更新重点为专家用户提供最大的灵活性，并修复顽固的推理 Bug（“飞点”、“空白掩码”）。**

- **解耦的模型架构**:
    - **问题**: 此前，定位器 (Locator) 和 SAM 分割器 (Segmenter) 被视为一个耦合的“模型”。这缺乏灵活性。
    - **解决方案**: UI 和 `AntEngine` 已重构，将 **定位器** 和 **分割器** 视为两个独立的、可互换的组件。
    - **UI 影响**: 用户现在在“AI 工作流”面板中有两个独立的下拉菜单：一个用于选择 `locator_*.pth`，另一个用于选择 `sam_decoder_lora_*.pth`。
- **混合推理策略**:
    - **新功能**: 分割器下拉菜单现在包含 **"Base SAM (Original)"** 选项。这允许用户将经过微调的、高精度的定位器与功能强大、通用性强的原始 SAM 结合使用。
    - **最佳实践**: 对于大多数用例，推荐的策略是：**训练一个强大的定位器**，并将其与 **Base SAM** 配对使用，以实现干净、鲁棒的分割，同时避免微调的副作用。
- **关键推理 Bug 修复**:
    - **修复“飞点”**: `SAMWorker` (用于魔棒/框选提示) 现在使用高级过滤。对于框提示，它只保留与提示框重叠的轮廓。对于点提示，它只保留包含点击点的轮廓，**彻底消除了“Z 字形”伪影和随机噪声点。**
    - **修复自动标注中的“空白掩码”**: 追踪到一个关键的坐标 Bug，该 Bug 会导致图像边缘附近对象的提示框计算不正确，从而导致 SAM 分割背景。逻辑现已加强，严格将框坐标裁剪到图像边界内，确保有效的提示。
    - **统一工具行为**: 魔棒 (`SAMWorker`) 现在可以正确加载选定的微调分割器权重，确保其行为与自动标注引擎一致。
- **UI/UX 增强**:
    - **实时项目统计**: “项目图片”面板现在显示 `(已标注 / 总数)` 的实时计数，提供项目进度的即时反馈。
    - **交互式验证报告**: 训练后的报告对话框现在包含一个滑块，可根据需要动态加载和查看特定百分比的验证图像，取代了之前预设的系统。

### **[2025-12-29] v3.3 精度与稳定性升级 ("感知尺寸"版)**
> **本次更新重点解决包围框不稳定（“漂移”与“过小”）以及 UI 同步的严重 Bug。**

- **混合定位器架构 (Hybrid Locator - ResNet + WH Regression)**:
    - **问题**: 此前模型仅依赖热力图的阈值来“猜测”框的大小。当热力图信号较弱时，生成的框会缩成极小的一个点（如 10x10像素）；且容易受背景纹理干扰产生漂移。
    - **解决方案**: 升级了神经网络 (`TraitRegressor`)，增加了一个并行的 **宽高回归头 (WH Regression Head)**。
    - **效果**: 模型现在能直接记忆并预测每个部位的物理尺寸。即使热力图很弱，预测出的框也能保持正确的大小（例如稳定输出一个 200px 的头部框），极大提升了 SAM 分割的成功率。
- **Focal Loss 损失函数**:
    - **问题**: 使用普通的 MSE Loss 时，模型在训练初期（前50轮）倾向于“偷懒”，预测全黑背景以降低误差，导致收敛极慢。
    - **解决方案**: 引入 **Focal MSE Loss**。这强迫模型关注那些稀疏的关键点（正样本），并对忽略目标的行为给予重罚。这显著加快了收敛速度，并解决了“把脚当头”的定位错误。
- **关键 Bug 修复**:
    - **UI 分类同步**: 修复了新建或打开项目时，UI 分类列表没有刷新的严重 Bug。此前用户虽然删除了部位，但后台仍按默认 5 分类运行，导致出现“幽灵标注”（只有1个部位却画出5个框）。
    - **权重加载安全**: 系统现在会严格检查模型架构的兼容性。杜绝了在不同分类数量（如 1类 vs 5类）的模型间切换时导致的静默错误或崩溃。
- **自动化实验报告 (Automated Reporting)**:
    - **论文级图表**: 训练结束后，系统会自动生成一个包含训练数据（CSV）、高质量曲线图（Loss/Error）和“视觉验证拼图”（真值 vs 预测对比）的报告文件夹。
    - **内置查看器**: 新增了报告查看弹窗，无需离开软件即可直接预览训练动态和验证集效果，方便科研人员快速评估模型质量。

### **[2025-12-26] v3.2 鲁棒性与动态控制升级 (灾后重建版)**
> **本次更新重点解决小样本训练(Few-Shot)中的过拟合与背景误触问题，并大幅优化了标注体验。**

- **鲁棒推理引擎 (Robust Inference Engine)**:
    - **底噪阈值 (Noise Floor)**: 引入 `thresh = max(peak * adapt, noise_floor)` 机制。这一关键更新有效防止了在模型置信度较低时（常见于少样本训练初期），背景噪音被错误放大为巨大的包围框。
    - **多边形自动瘦身 (Polygon Simplification)**: 在推理流程中集成了 `cv2.approxPolyDP` 算法。SAM 生成的原始多边形（通常包含数千个点）现在会根据用户可调的“多边形简化度”参数自动简化。这不仅生成了更清爽、轻量且易于人工微调的标注，还显著提升了 UI 在处理大量标注时的性能。
- **动态训练控制 (Dynamic Training Controls)**:
    - **UI 参数调节**: 用户现在可以在“模型设置”对话框中直接调整 `Epochs` (轮数)、`Learning Rate` (学习率) 和 `Weight Decay` (权重衰减)，无需修改代码。
    - **实时训练日志**: 修复了 UI 信号连接，现在的训练 Loss、Error 值和进度条可以实时刷新显示。
- **实验灵活性**:
    - 新增 **"Base SAM (Reset)"** 模式。用户可以通过模型下拉菜单选择是进行增量训练（微调），还是重置权重从头训练。
- **系统稳定性**:
    - **编码修复**: 彻底修复了中文 UI 的乱码问题，恢复 UTF-8 编码。
    - **持久化修复**: 项目分类体系和设置现在会在修改时立即保存，防止重启后数据丢失。

### **[2025-12-24] v3.1 自适应热力图系统 (Adaptive Heatmap)**
- **核心算法重构**:
    - **预测引擎**: 摒弃了旧版的“中心点+固定比例框”逻辑。现在使用**热力图光斑分析 (Heatmap Blob Analysis)**，能够根据热力图的实际覆盖范围动态生成包围盒 (Dynamic Bounding Box)。
    - **自适应训练**: 改进了 `Dataset` 生成逻辑，引入**动态 Sigma (Dynamic Sigma)**。训练时热力图光斑大小不再固定，而是随标注目标的物理尺寸自动缩放。
    - **效果**: 完美解决了**大头蚁 (Pheidole)** 兵蚁头部过大导致截断的问题，同时也保证了微小器官（如复眼）的框体紧凑，避免背景干扰。实现了真正的“大虫大框，小虫小框”。

### **[2025-12-18] v3.0 关键逻辑修复 (Critical Fixes)**
- **修复“哈哈镜”畸变问题**：为定位器模型 (Locator CNN) 实现了“信箱模式 (Letterbox)”调整大小（即填充黑边）。此前，图片会被强制拉伸至 512x512，导致非正方形图片出现坐标预测偏差。
- **动态 SAM 提示框**：将固定大小的提示框替换为**动态百分比框**（约占图片宽度的 31%）。这解决了以下问题：
    - 对于大部位（如大头蚁头部），固定框太小。
    - 对于小部位，固定框太大。
    - 过大的框导致 SAM 选中“整只蚂蚁”而不是特定部位。
- **统一流水线**：确保训练流水线 (`dataset.py`) 和推理流水线 (`engine.py`) 现在使用完全一致的坐标变换逻辑。

### **[2025-12-18] v1.0: Formica-Flow 诞生（前正式版记录）**
- **品牌重塑**：项目正式更名为 **Formica-Flow**。
- **多模态融合**:
    - 将 **Auto-Label-Trainer**（标注端）与 **Literature Mining**（文献端）合并。
    - 新增 `core/pdf_processor` 模块，集成 `poppler` 工具。
    - 首次实现 **“PDF -> 筛选 -> 提取图片 -> 标注 -> 训练”** 的全流程闭环。

### **[2025-12-10 15:36] v0.7: 多物种与动态分类学适配（前正式版记录）**
- **架构重构**：移除了硬编码的身体部位列表（`Head`、`Mesosoma` 等）。
- **动态化**：
    - 支持用户在 UI 中动态 **添加/删除** 身体部位。
    - `taxonomy.db` 结构升级，支持多物种描述管理。
    - Locator 模型现在会根据当前 taxonomy 动态调整输出通道数。
- **国际化**：中英文支持增强，未翻译的自定义部位按原样显示。

### **[2025-12-10 15:08] v0.6: 智能裁剪与项目分割（前正式版记录）**
- **新工具**：引入 **Smart Cropper（智能裁剪器）**。
    - 支持从整版图（Plate）中快速切出多张单体图。
    - 裁剪后图片可以自动归属到当前项目。
- **工作流优化**：解决了多视图图片位于同一原始图中的标注难题。

### **[2025-12-09 18:01] v0.5: 文档与规范（前正式版记录）**
- **文档体系**：首次创建 `LLM_CONTEXT.md`，为 AI 辅助开发提供标准化项目架构文档。
- **训练流程稳定化**：进一步优化模型训练流程控制，提升迭代稳定性。

### **[2025-12-09 17:16] v0.4: 训练可视化（前正式版记录）**
- **新增功能**：在 `AntEngine` 中实现 `plot_full_report`。
- **可视化**：新增 4 Panel 训练仪表盘，实时展示：
    1. Training / Validation Loss 曲线。
    2. Locator 热力图预测效果。
    3. SAM 分割掩膜对比（GT vs Pred）。
    4. 关键指标（Pixel Error 与 mIoU）。
- **意义**：训练过程不再是黑盒，用户可以直接观察模型收敛情况。

### **[2025-12-09 16:42] v0.3: 高精度 SAM 迭代（前正式版记录）**
- **核心修复**：修复了 SAM 训练难以收敛的严重问题。
    - **Normalization**：在 `TwoStageDataset` 中强制加入 ImageNet 标准化，以匹配 SAM 预训练权重的数据分布。
- **架构调整**：重构训练循环，绕过 `ultralytics` 封装层，直接操作底层 PyTorch `sam_model`，解决 `KeyError: 'model'` 与梯度更新失效问题。
- **性能提升**：优化显存管理，在 `parts` 模式训练时强制限制 `batch_size=2` 以适配 24G 显存。

### **[2025-12-09 15:40] v0.2: 形态测量工具（前正式版记录）**
- **科学工具**：新增 **Scale Tool（标尺工具）**，支持用户通过绘制参考线进行像素/毫米校准。
- **自动测量**：集成 `cv2.contourArea` 与 `cv2.arcLength`，实现对标注区域 **面积 ($mm^2$)** 和 **周长 ($mm$)** 的自动计算。
- **UI 改进**：在右侧面板增加 **Measurements** 分组，仅在启用形态测量时显示。

### **[2025-11-20] v0.1: 基础架构（前正式版记录）**
- **创作思路与核心逻辑**：
    - **高分辨率悖论**：
        - 常规视觉模型（如 YOLOv8）通常强制把输入压缩到 640x640。
        - 对昆虫分类学而言，这会毁掉很多只占整图极小比例的关键形态特征。
        - **决策**：放弃单阶段检测路线，必须保留原图分辨率进入推理逻辑。
    - **仿生学注意力设计**：
        - 工作流模拟分类学家在显微镜下的操作：先快速找大区域，再放大看细节。
        - **架构确立**：**Locator** 负责低倍定位，**Segmenter / SAM** 负责在高分辨率局部区域上做精细交互分割。
    - **交互哲学**：
        - 标注过程高度重复，如果工具卡顿，用户体验会迅速崩塌。
        - **技术选型**：放弃 Web-first 标注路线，改用 **PySide6 (Qt)** 原生工作台，结合 `QGraphicsScene` 与 `QThread` 处理大图渲染和 AI 线程分离。
- **具体实现细节**：
    - **模型层**：
        - **Stage 1 (Locator)**：自研轻量 CNN `TraitRegressor`，输出 6 通道 Gaussian Heatmaps。
        - **Stage 2 (Segmenter / SAM Integration)**：
            - 引入 Meta 的 **Segment Anything Model (SAM)** 作为核心交互引擎。
            - 为适配 24G 显卡上的训练/推理流程，底层加入 `model.eval()` 约束、显式梯度管理，并重写 `dataset.py` 支持动态 ROI 裁剪。
    - **数据层**：
        - `ProjectManager` 在保存时强制计算相对路径，保证项目在不同电脑之间可迁移。
        - 采用 **JSON + SQLite** 的双层持久化：JSON 负责图像/项目索引，SQLite 负责结构化分类学描述。

- 如需查看按实际创建时间重建后的完整前期迭代，请直接阅读：
  - `HISTORY_PRE_RELEASE.md`

---

## 🌟 核心功能

### 1. 📄 文献处理 (PDF Processing)
*   **智能筛选**：默认使用 V2 的“CSV先行 + 全量LLM校验”流程，将 PDF 分类为“新种报告”或“无关文献”；原规则优先流程作为 `legacy` 明确保留，可随时回退。
*   **数据提取**：自动从论文中提取标本图片，并利用空间算法关联对应的图注（Caption）和描述文本。
*   **便携式 OCR**：内置 OCR 支持，无需繁琐配置即可处理扫描版老旧文献。
*   **数据库浏览**：内置可视化工具，直接查看提取的图片和文本对应关系。
*   **JSONL 导出**：一键生成用于多模态大模型（VLM）微调的图文对数据集。

### 2. 🏷️ 标注工作台 (Labeling Workbench)
*   **AI 辅助标注**：
    *   **魔棒 (Magic Wand)**：基于 SAM 模型，点击即可自动分割身体部位。
    *   **框选 (Box Prompt)**：拖拽矩形框，自动识别并分割目标区域。
    *   **自动标注 (Auto)**：运行训练好的模型，批量自动标注新图片。
*   **动态分类体系**：不再局限于固定的身体部位，你可以自由添加如“翅膀”、“触角柄”等部位，系统会自动适应。
*   **形态测量**：内置标尺工具，自动计算标注部位的真实面积 ($mm^2$) 和周长 ($mm$)。

### 3. 🧠 模型训练
*   **一键训练**：在本地 GPU (推荐 RTX 3090/4090) 上训练定制化的 **定位器 (Locator)** 和 **分割器 (Segmenter)**。
*   **数据导出**：支持导出标准的 **COCO** 或 **YOLO** 格式数据集。

---

## 🚀 安装指南

### 1. 环境要求
*   Windows 10/11 (推荐)
*   Python 3.10+
*   NVIDIA 显卡 (强烈推荐，用于加速 SAM 和训练)

### 2. 安装依赖
```bash
# 1. 安装 PyTorch (建议使用官方命令安装 CUDA 版本)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# 2. 安装项目依赖
pip install -r requirements.txt
```

### 3. 配置外部工具 (Poppler)
**PDF 处理功能必须步骤**：
1.  下载 Windows 版 `Poppler` (例如 [Release-24.02.0-0.zip](https://github.com/oschwartz10612/poppler-windows/releases/))。
2.  解压压缩包。
3.  将解压后的**所有内容**（特别是包含 `bin` 的目录）复制到项目目录：
    `auto-label-trainer/external_tools/poppler/`
    *   *正确路径示例：* `external_tools/poppler/Library/bin/pdftoppm.exe`
    *   **注意**：无需配置系统环境变量，程序会自动识别。

### 4. 下载模型权重
下载 SAM Base 模型 (`sam_b.pt`) 并放入 `auto-label-trainer/AntSleap/weights/` 目录。

---

## 🎮 使用指南

启动主程序：
```bash
python AntSleap/main.py
```

### 流程 A：文献处理
1.  切换到 **"PDF Processing" (文献处理)** 标签页。
2.  **筛选**：选择 PDF 所在的文件夹 -> 点击 "Start Classification Batch"。
3.  **提取**：选择筛选出的 "New Species" 文件夹 -> 点击 "Start Extraction Pipeline"。
4.  **浏览**：点击 "Browse Database" 查看提取结果。

### 流程 B：标注与训练
1.  切换到 **"Labeling Workbench" (标注工作台)** 标签页。
2.  **导入**：拖入图片（或从 PDF 提取结果中导入）。
3.  **标注**：使用魔棒工具快速标记身体部位。
4.  **训练**：点击 "Train Models" 训练你的专属 AI。

### 流程 C：候选数据核验（当前实操路径）
1.  先按原流程完成 PDF 提取，并通过 **Browse Database** 看图文记录。
2.  导出候选池产物：
    ```bash
    python tools/governance/export_pdf_candidates.py --db ant_literature.db --out artifacts/core2/pdf_candidates_raw.json --mode candidate_only
    ```
3.  生成优先级与分流报告：
    ```bash
    python tools/governance/build_sampling_plan.py --candidates artifacts/core2/pdf_candidates_raw.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/review_sampling_report.json
    python tools/governance/route_candidates.py --candidates artifacts/core2/pdf_candidates_raw.json --policy AntSleap/config/view_policy_core2.json --out artifacts/core2/routing_decisions.json
    ```
4.  人工确认后，再把你认可的图片手动导入项目进行标注训练。

### 流程 D：一键治理验收
```bash
python tools/governance/run_core2_pipeline.py --project test-head.json --db ant_literature.db --policy AntSleap/config/view_policy_core2.json --out artifacts/core2
```

---

## 📂 项目结构
*   `AntSleap/main.py`: 程序入口，负责 UI、线程调度和配置管理。
*   `AntSleap/core/governance/`: Core-2 治理核心（策略、切分、评估、分流、触发器）。
*   `core/pdf_processor/`: PDF 处理核心逻辑（分类、提取）。
*   `core/engine.py`: AI 训练核心逻辑（定位器、SAM、推理流水线）。
*   `core/project.py`: 数据管理（JSON 持久化、COCO/YOLO 导出）。
*   `tools/governance/`: 治理脚本、验收套件与一键流水线。
*   `docs/core2_governance_runbook.md`: 治理命令链与验收映射。
*   `LLM_CONTEXT.md`: 给 AI 助手阅读的技术文档。
*   `LLM_CONTEXT_DETAILED.md`: 深度技术上下文与接力文档。

## 📄 许可证
MIT License.


---

# 版本演进历史 (2025.11 - 2025.12.18)

本文档补全了 `Formica-Flow 1.0` 发布之前的开发迭代日志。基于项目备份文件结构重建，已按**实际创建时间**校正顺序。

---

## 📅 前期开发阶段 (Auto-Label-Trainer)

### v0.1: 基础架构 (Base / Origin Story)
*   **时间**: 2025-11-20
*   **创作思路与核心逻辑 (The Creation Logic)**:
    *   **痛点分析 (The High-Res Paradox)**: 
        *   常规 AI 视觉模型（如 YOLOv8）通常强制将输入压缩至 640x640。对于昆虫分类学而言，这不仅是信息的丢失，更是“毁灭性”的——蚂蚁的辨识特征（如触角窝的形状、胸部的绒毛分布）往往只占整图的 0.1%。
        *   *决策*: 坚决摒弃“单阶段检测”方案。必须保留原图分辨率进行推理。
    *   **仿生学设计 (Biomimetic Attention)**:
        *   模拟分类学家在显微镜下的操作流：先用低倍镜快速寻找目标（Head/Thorax），锁定视野后再切换高倍镜观察细节。
        *   *架构确立*: **Locator (定位器)** 充当“低倍镜”，负责在降采样图中寻找热力图中心；**Segmenter (分割器)** 充当“高倍镜”，在裁剪出的高清切片上进行像素级分割。
    *   **交互哲学 (UX Philosophy)**:
        *   标注过程极其枯燥。如果工具卡顿，用户体验会崩塌。
        *   *技术选型*: 放弃 Web 方案（Label Studio 等在加载 50MB 本地大图时有延迟），选择 **PySide6 (Qt)** 原生开发。利用 `QGraphicsScene` 的 BSP 树索引处理超大图渲染，利用 `QThread` 将 AI 推理完全剥离主线程，确保“界面永不卡死”。

*   **具体实现细节 (Implementation Details)**:
    *   **模型层 (The Dual-Engine)**:
        *   **Stage 1 (Locator)**: 自研 `TraitRegressor` (基于轻量级 CNN)，输出 6 通道 **Gaussian Heatmaps**。
            *   *Trick*: 为什么不用 BBox 回归？因为蚂蚁身体极其扭曲，热力图中心点比 BBox 中心更稳定，且对遮挡更鲁棒。
        *   **Stage 2 (Segmenter - SAM Integration)**:
            *   引入 Meta 的 **Segment Anything Model (SAM)** 作为核心交互引擎。
            *   *工程挑战*: SAM 的 `ViT-B` 编码器极其吃显存。为了在 24G 显存上同时跑训练和推理，我们在代码底层强制执行了 `model.eval()` 和梯度的手动管理，并重写了 `dataset.py` 以支持动态 ROI 裁剪 (Dynamic ROI Cropping)。
    *   **数据层 (Data Persistence)**:
        *   **相对路径强制化**: 考虑到数据集会在不同研究人员/电脑间流转，`ProjectManager` 被设计为在保存时自动计算 `os.path.relpath`，杜绝了绝对路径导致的“文件丢失”噩梦。
        *   **双库异构**: 图像索引存 JSON (轻量/易读)，分类学描述存 SQLite (结构化/易查询)。

### v0.2: 形态测量工具 (Morphometrics / Area Calc)
*   **时间**: 2025-12-09 15:40
*   **科学工具**: 新增 **Scale Tool (标尺工具)**，支持用户通过绘制参考线进行像素/毫米校准。
*   **自动测量**: 集成 `cv2.contourArea` 和 `cv2.arcLength`，实现了对标注区域的 **面积 ($mm^2$)** 和 **周长 ($mm$)** 的实时计算。
*   **UI改进**: 在右侧面板增加了 "Measurements" 分组，仅在启用形态测量时显示。

### v0.3: 高精度 SAM 迭代 (High-Precision SAM)
*   **时间**: 2025-12-09 16:42
*   **核心修复**: 修复了 SAM 训练难以收敛的严重 Bug。
    *   **Normalization**: 在 `TwoStageDataset` 中强制加入 ImageNet 标准化 (`TF.normalize`)，匹配 SAM 预训练权重的数据分布。
*   **架构调整**: 重构训练循环，绕过 `ultralytics` 封装层，直接操作底层的 PyTorch `sam_model`，解决了 `KeyError: 'model'` 和梯度更新失效的问题。
*   **性能提升**: 显存管理优化，在训练 `parts` 模式时强制限制 `batch_size=2` 以适配 24G 显存。

### v0.4: 训练可视化 (Training Visualization)
*   **时间**: 2025-12-09 17:16
*   **新增功能**: 在 `AntEngine` 中实现了 `plot_full_report` 方法。
*   **可视化**: 新增训练过程的 4-Panel 仪表盘，实时展示：
    1.  Training/Validation Loss 曲线。
    2.  Locator 热力图预测效果。
    3.  SAM 分割掩膜对比 (GT vs Pred)。
    4.  关键指标 (Pixel Error & mIoU)。
*   **意义**: 解决了训练过程"黑盒"的问题，允许用户直观评估模型收敛情况。

### v0.5: 文档与规范 (LLM Context)
*   **时间**: 2025-12-09 18:01
*   **文档体系**: 首次创建 `LLM_CONTEXT.md`，为 AI 辅助开发提供了标准化的项目架构文档。
*   **模型迭代框**: 进一步优化了模型训练的流程控制，确保迭代过程的稳定性。

### v0.6: 智能裁剪与项目分割 (Smart Cropper)
*   **时间**: 2025-12-10 15:08
*   **新工具**: 引入 **Smart Cropper (智能裁剪器)**。
    *   支持从整版图 (Plate) 中快速切分出多张单体图。
    *   实现了裁剪后图片自动从属于当前项目的功能。
*   **工作流优化**: 解决了多视图（背视/侧视）图片在同一文件中的标注难题。

### v0.7: 多物种与动态分类学适配 (Dynamic Taxonomy)
*   **时间**: 2025-12-10 15:36
*   **架构重构**: 移除了硬编码的身体部位列表 (Head, Mesosoma, etc.)。
*   **动态化**:
    *   支持用户在 UI 中动态 **添加/删除** 身体部位。
    *   `taxonomy.db` 结构升级，支持多物种 (Multi-Species) 的描述管理。
    *   Locator 模型现在会根据当前的 Taxonomy 动态调整输出通道数。
*   **国际化**: 增强了中英文多语言支持 (`i18n`)，未翻译的自定义部位将按原样显示。

---

## 🚀 正式发布阶段 (Formica-Flow)

### v1.0: Formica-Flow 诞生
*   **时间**: 2025-12-18
*   **品牌重塑**: 项目正式更名为 **Formica-Flow**。
*   **多模态融合**:
    *   将 **Auto-Label-Trainer** (标注端) 与 **Literature Mining** (文献端) 合并。
    *   新增 `core/pdf_processor` 模块，集成 `poppler` 工具。
    *   实现了 "PDF -> 筛选 -> 提取图片 -> 标注 -> 训练" 的全流程闭环。

