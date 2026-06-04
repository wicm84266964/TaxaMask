# TIF GPU 体预览实施记录

> 日期：2026-05-29  
> 最近同步：2026-06-04
> 范围：TIF Volume Workbench 的只读 3D volume 预览、清晰模式、内部观察和 GPU/CPU 回退。

## 1. 研究需求

这次改动来自蚂蚁 TIF / micro-CT 内部结构观察需求。用户希望在不先转 STL 的情况下，直接基于 TIF volume 旋转查看、放大、进入体内，并为后续脑部方向统一和重新切片做准备。

需要特别区分两件事：

- 3D 体预览：帮助研究者理解当前 specimen 的整体朝向和内部结构位置。
- 标准化重切片：把不同 specimen 按同一脑部方向重新采样成新的 volume，供结构分析或 AI 训练。

本次完成的是第一项；第二项还未实现。

## 2. 已实现内容

- 新增 `AntSleap/ui/tif_gpu_volume_canvas.py`，当前默认使用离屏 GPU 体渲染：OpenGL context / FBO 在后台完成 ray marching，结果读回普通 Qt 显示控件。
- 旧版嵌入式 `QOpenGLWidget` 体预览路径不再作为默认路线，只保留为显式兼容/诊断路径，避免和内嵌 Ant-Code WebEngine / Qt Quick 在同一个顶层窗口里争抢图形合成后端。
- `TifWorkbenchWidget` 在支持 Qt OpenGL 和 PyOpenGL 时使用离屏 GPU ray marching；否则自动回退到 CPU 预览。
- 新增 `PyOpenGL>=3.1.7` 依赖。
- 新增 `tools/start_antsleap_high_performance_gpu.ps1`，用于在 Windows 上以高性能 GPU 相关环境变量启动 TaxaMask。
- GPU 预览支持：
  - 3D texture 上传
  - GLSL ray marching
  - front-to-back 透明度累积
  - 多种投影/渲染模式：Composite、MIP、MinIP、Average、Surface
  - 密度阈值
  - 梯度辅助着色
  - 近端剖切
  - 视点深度
  - 拖动低质量 / 静止高清双模式
- 静止且放大观察时支持 `ROI high detail`：通过更高离屏像素密度渲染当前视野，再缩回显示区域，用于观察小部位细节；ROI 倍率滑杆范围为 1.0x 到 3.0x。
- 清晰模式在静止高清时尽量保留 `uint16` 源强度，并使用更锐利的采样策略。
- 体纹理最大边长和光线采样上限均提升到 4096。
- 画布叠加状态显示 GPU 名称、纹理、采样、视点、近端切、缩放、平移、显存估算、上传/绘制耗时和数据类型。
- 中文 UI 已将体预览指标和 tooltip 中文化，避免中文模式混入英文指标。

## 3. 交互约定

- 左键拖动：旋转。
- 右键拖动：平移，方向按“抓住图像拖动”理解。
- 滚轮：缩放，最高 16x。
- `Render mode / 渲染模式`：在 Composite、MIP、MinIP、Average、Surface 之间切换观察方式。
- `ROI high detail / ROI 高清`：只在 GPU、静止、放大观察时生效，用更高离屏采样改善局部清晰度。
- 视点深度：移动观察点进入体数据，不删除任何体素。
- 近端剖切：从当前屏幕近端切掉遮挡组织，便于看内部。
- 重置 3D 视角：恢复默认外部视角，并清空视点深度和近端剖切。

## 4. 数据和标签边界

- 3D 体预览是只读观察层。
- 它不写入 `working_edit`、`manual_truth` 或 `model_draft`。
- 精确 material ID 修改仍必须回到 `切片复核`。
- 标签层如果未来进入斜切片/重切片输出，必须用最近邻插值，不能用图像线性插值。

## 5. 已知限制

- GPU 预览仍然是显示用渲染，不是定量分析结果。
- 如果原始 TIF 很大，拖动时会用较低纹理，停下后才切回静止高清。
- ROI 高清是观察层超采样，不是标签 ROI 裁剪、训练体裁剪或定量重建。
- Windows 混合显卡机器可能仍由系统选择核显；启动脚本只能帮助设置环境变量，不能完全替代 Windows/NVIDIA 控制面板设置。
- Qt 退出阶段偶尔仍可能出现 `QDxgiVSyncService not destroyed in time` 等提示，目前视为不影响使用的 OpenGL/Qt teardown 信息。
- 还没有实现脑部标准化重切片、训练用 ROI 裁剪或统一朝向训练体导出。

## 6. 验证记录

本阶段的核心验证命令：

```powershell
C:\Users\admin\anaconda3\envs\antsleap\python.exe -m unittest tests.test_tif_project tests.test_tif_stack_import tests.test_tif_export tests.test_tif_prediction_import tests.test_tif_gpu_volume_canvas tests.test_tif_workbench
```

最近一次结果：55 个测试通过。

## 7. 下一阶段建议

下一步不建议做“当前屏幕截图式切片”，而应做脑部标准化重切片：

- 让用户为每只 specimen 标定脑/头部中心。
- 标定头顶方向和前后方向；仅有“头顶向上”仍会留下绕该轴旋转的不确定性。
- 使用原始 `spacing_zyx` 计算 3D affine transform。
- 图像体用线性或三次插值。
- 标签体用最近邻插值。
- 输出新的标准化脑部 volume，并保留来源 specimen、旋转参数、ROI、spacing 和插值方式。
