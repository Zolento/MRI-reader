# MRI Reader

[English](README_en.md) | [中文](README.md)

基于Qt和Python的MRI图像查看和处理工具，支持2D/3D图像和k-space数据。

## 功能特性

### 核心功能
- 智能数据检测：自动识别2D/3D，可选图像/k-space数据类型
- k-space转换：支持2D逐切片IFFT和3D完整IFFT转换
- 多格式支持：读取.npy文件，保存为.jpg/.png格式
- 多视角显示：3D数据支持横截面(Axial)、矢状面(Sagittal)、冠状面(Coronal)
- RSS通道合并：多通道数据自动使用Root Sum of Squares方法合并

### 图像增强操作
- 对比度调整：0.1x - 5.0x范围，滑块+数值框精确控制
- 亮度调节：-1.0 - +1.0范围，实时预览
- Log变换：专门用于查看k-space数据
- 旋转：任意角度(-180度至180度)和快捷90度倍数旋转
- 缩放：0.1x - 5.0x，支持鼠标滚轮缩放
- 翻转：水平和垂直翻转

### 3D导航
- 滑动条：直观选择切片位置
- 按钮导航：前/后/首/末切片快捷按钮
- 键盘支持：方向键快速切换切片
- 鼠标滚轮：在3D模式下滚轮切换切片
- 点击选择：在图像上点击选择切片

## 系统要求

- 操作系统：Linux (优先适配), Windows, macOS
- Python: >= 3.9
- 包管理：uv (推荐) 或 pip

## 快速开始

### 1. 安装uv (如未安装)

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用pip
pip install uv
```

### 2. 配置环境

```bash
# 进入项目目录
cd mri-reader

# 运行环境配置脚本
./setup.sh
```

### 3. 运行程序

```bash
# 方法1: 使用uv直接运行
uv run python -m src.main

# 方法2: 快速启动脚本
./run.sh
```

### 4. 生成测试数据 (可选)

```bash
# 生成测试数据用于验证功能
uv run python generate_test_data.py
```

这将生成测试文件到 `test_data/` 目录，包含2D/3D图像和k-space数据。

## 使用说明

### 界面布局

```
+----------------+----------------+-----------+
|   K-Space显示   |    图像显示     | 增强面板  |
|    (左侧)      |    (中间)      |  (右侧)   |
+----------------+----------------+           |
+----------------------------------+-----------+
|        切片/视角导航 (底部)                  |
+----------------------------------------------+
```

### 打开文件
1. 点击菜单栏 `文件` -> `打开` 或按 `Ctrl+O`
2. 选择 `.npy` 格式的MRI数据文件
3. 程序自动检测数据类型并显示

### 保存图像
1. 点击菜单栏 `文件` -> `保存为JPG` 或按 `Ctrl+S`
2. 选择保存路径和格式 (JPG/PNG)
3. 当前显示的图像将被保存

### 增强操作
1. 在右侧面板顶部选择增强目标：K-Space 或 Image
2. 调整各项参数（每个目标参数独立保存）：
   - 拖动滑块或输入数值调整对比度/亮度
   - 勾选Log变换查看k-space
   - 设置旋转角度或使用快捷按钮
3. 点击"重置所有"恢复当前目标的默认设置

### 3D数据导航
- 使用底部滑动条选择切片
- 点击标签页切换视角 (横截面/矢状面/冠状面)
- 使用键盘方向键快速浏览切片
- 鼠标滚轮切换切片 (按住Ctrl键缩放)

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+O | 打开文件 |
| Ctrl+S | 保存图像 |
| Ctrl+R | 重置当前目标设置 |
| Ctrl+0 | 适应窗口大小 |
| Ctrl++ | 放大 |
| Ctrl+- | 缩小 |
| 方向键 | 切换切片 (3D模式) |
| Ctrl+鼠标滚轮 | 缩放图像 |

## 项目结构

```
mri-reader/
├── pyproject.toml              # 项目配置和依赖
├── setup.sh                    # 环境配置脚本
├── run.sh                      # 快速启动脚本
├── generate_test_data.py       # 测试数据生成器
├── README.md                   # 中文说明文档
├── README_en.md                # English documentation
├── src/
│   ├── main.py                 # 程序入口
│   ├── main_window.py          # 主窗口
│   ├── core/
│   │   ├── mri_data.py         # MRI数据模型和自动检测
│   │   ├── kspace_converter.py # k-space FFT转换
│   │   └── image_processor.py  # 图像增强处理
│   └── ui/
│       ├── image_canvas.py     # 图像显示画布
│       ├── enhancement_panel.py # 增强操作面板
│       └── slice_navigator.py  # 切片导航器
└── test_data/                  # 测试数据目录 (git忽略)
```

## 数据格式说明

### 支持的输入格式

支持以下文件格式：

- **NumPy (.npy)**: 直接读取.npy文件
- **MAT (.mat)**: 读取MATLAB .mat文件，支持多数据键(key)选择

程序自动检测以下数据形状：

1. 2D图像：(height, width) 或 (slices, height, width)
2. 3D图像：(channels, slices, height, width)
3. 2D k-space：(phase, freq) (复数数据)
4. 3D k-space：(channels, slices, phase, freq) (复数数据)

### 加载流程

1. 选择 .npy 或 .mat 文件
2. 选择数据类型：K-Space (频域) / Image (图像)
3. 如果是 .mat 文件，选择数据键 (key)
4. 自动处理并显示

### K-Space 转换

- 2D模式：逐切片执行 2D IFFT
- 3D模式：在相位和频率维度执行 IFFT（正交归一化）

## 技术栈

- GUI框架：PyQt5 - 成熟的跨平台GUI库
- 数值计算：NumPy - 数组操作和数学运算
- 科学计算：SciPy - 图像旋转和缩放
- 图像处理：Pillow - 图像保存支持

## 开发指南

### 添加新依赖

```bash
uv pip install package_name
# 并更新pyproject.toml
```

### 扩展功能

1. 添加新的图像增强：在 `ImageProcessor` 类中添加方法
2. 添加新的UI组件：在对应 `ui/` 模块中创建组件
3. 支持新数据格式：扩展 `MRIData` 类的检测方法

## 许可证

本项目仅供学习和研究使用。
