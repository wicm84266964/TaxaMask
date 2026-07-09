# Local Axis Reslice 设计

## 定位

Local Axis Reslice 是 TIF/CT 工作台中的局部坐标系重切片流程。它最初由 AntScan 脑部/头部方向问题推动，但底层设计应保持通用，不应命名或实现为 brain-only workflow。

目标是：在已经提取出的 part volume 上定义可保存、可复核、可重现的局部坐标系，然后导出沿该坐标系重采样的 reslice volume。

## 为什么需要 Local Axis

AntScan 或其他 CT 数据中，原始 TIF stack 的 Z 轴不一定对应生物体的稳定解剖轴：

- 标本姿态可能不同。
- 小个体和大个体的扫描容器不同。
- 有些样本沿体轴切片，有些样本横向切片。
- 原始 Z 轴不能稳定代表头尾或局部结构方向。

因此，内部结构研究不能只依赖原始切片方向。研究者需要在 part volume 中定义局部坐标系。

## 核心概念

```text
source Z axis
-> editable output axis
-> origin
-> roll reference points
-> local frame
-> reslice output
```

- source Z axis：原始 stack 的切片方向，只读参考。
- editable output axis：用户要导出的局部切片推进轴。
- origin：局部坐标系中心。
- roll reference points：决定绕 output axis 的旋转方向。
- local frame：完整 x/y/z 轴、spacing、origin 和 provenance。
- reslice output：保存到 part 下的派生输出。

## 三点参考

当前 UI 支持通过观察侧剖切面选择三个 roll reference 点。三个点定义参考平面，输出轴可以对齐为垂直于该平面。

设计要求：

- 三点选择必须绑定当前 specimen / part。
- 切换 specimen / part / reslice 后，旧草稿不能误用。
- preview busy lock 不应阻止合法的三点草稿交互。
- 用户应能清除、重选、对齐和导出。

## 数据保存原则

Local Axis reslice 是派生数据：

- 不修改原始 TIF stack。
- 不修改 part source image。
- 输出保存为 part 下的 reslice 记录。
- metadata 保存 source provenance、local frame、spacing、shape 和参数。
- label volume 重切片应使用 nearest-neighbor 插值，避免 label ID 被灰度插值污染。

## AI proposal 边界

Local Axis 后端可以提出两类建议：

- global ROI proposal：目标部位候选区域。
- local frame proposal：局部坐标系候选。

但 AI 不应直接生成最终正式 reslice，也不应直接修改项目主记录。TaxaMask 应把 AI 输出导入为 proposal，由研究者复核后再接受。

## 与 TIF volume backend 的区别

TIF volume segmentation backend 输出 label prediction。Local Axis backend 输出 ROI/frame proposal。二者都走 contract/result/manifest 机制，但输出语义不同。

共同规则：

- TaxaMask 写 contract。
- 后端读 contract 执行任务。
- 后端写 result JSON。
- TaxaMask 导入 result 为可复核状态。
- 用户确认后才进入正式研究流程。

## 验收重点

Local Axis 的人工验收应按一条完整链路执行：

1. 选择 part。
2. 打开 3D preview。
3. 开启观察侧剖切面。
4. 选择三个参考点。
5. 对齐 output axis。
6. 导出 reslice。
7. 在项目树中打开新 reslice。
8. 保存项目并重开。
9. 确认 reslice、metadata 和可视状态仍存在。

这条链路不能只用单元测试替代，因为它涉及真实 GPU/Qt 交互和研究者视觉判断。
