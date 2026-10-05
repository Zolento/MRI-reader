# MRI Reader

[English](README_en.md) | [中文](README.md)

一个轻量的 MRI 数据速览器。在深度学习的数据管线里，用它快速打开 `.npy` / `.h5` / `.mat`，
确认形状和维度含义、看一眼图像或 k-space，必要时按正确的采集方式做 IFFT 重建出图。

> 它不是临床阅片软件，也不做定量分析。它只负责「看一眼，确认这份数据没问题」。

## 它解决什么问题

调试 MRI 模型时，下面这些问题几乎每次都要回答：

- 这份数据是**图像域**还是 **k-space**？
- 形状 `(C, S, H, W)` 里哪个是线圈、哪个是切片？4D 数据是 `(Coil, Slice)` 还是 `(Slice, Coil)`？
- k-space 做 IFFT 之后图像长什么样？该按 **2D 逐层采集**还是 **3D 体积采集**来重建？
- 多线圈数据用 RSS 合并后正常吗？是不是某几层坏掉了？

MRI Reader 就是为这些「看一眼」的场景做的：把文件拖进去 → 选两个选项 → 方向键翻层。

## 快速开始

```bash
pip install -e ".[dev]"      # 安装（含 pytest / ruff / black）
python -m src.main           # 或 ./run.sh，或安装后的 mri-reader
```

支持直接把文件**拖进窗口**。

## 支持的输入

| 格式 | 说明 |
|------|------|
| `.npy` | 单个数组，直接读取 |
| `.h5` / `.hdf5` | 选择数据集（例如 ISMRMRD 风格文件里的 `kspace` / `reconstruction_rss`） |
| `.mat` | 选择变量 key |

打开后需要你确认三件事：

1. **数据类型**：`Image`（图像域）还是 `K-Space`（频域）
2. **采集方式**（仅 k-space）：`2D 采集`（逐层 2D IFFT，默认）或 `3D 采集`（体积 3D IFFT）
3. **维度解释**：4D 数据是 `(Coil, Slice, H, W)` 还是 `(Slice, Coil, H, W)`；3D 数据第一维是线圈还是切片

程序内部一律归一化为 `(C, S, H, W)`：

| 轴 | 含义 |
|----|------|
| C | 线圈通道 |
| S | 切片（上下） |
| H | 行（前后） |
| W | 列（左右） |

| 原始形状 | 你选择的解释 | 内部形状 | 维度 |
|---|---|---|---|
| `(H, W)` | — | `(1, 1, H, W)` | 2D |
| `(X, H, W)` | `(Coil, H, W)` | `(X, 1, H, W)` | 2D |
| `(X, H, W)` | `(Slice, H, W)` | `(1, X, H, W)` | 3D |
| `(C, S, H, W)` | `(Coil, Slice, H, W)` | 原样 | 3D |
| `(S, C, H, W)` | `(Slice, Coil, H, W)` | 转置为 `(C, S, H, W)` | 3D |

三个视角分别固定一个轴（`src/core/views.py` 是唯一权威）：

| 视角 | 固定轴 | 平面形状 | 索引范围 |
|---|---|---|---|
| Axial 横截面 | S | `(H, W)` | `0 .. S-1` |
| Sagittal 矢状面 | W | `(S, H)` | `0 .. W-1` |
| Coronal 冠状面 | H | `(S, W)` | `0 .. H-1` |

## k-space 重建

| 采集方式 | 处理粒度 | IFFT 轴 |
|---|---|---|
| 2D 采集（默认） | 每个 `(coil, slice)` 独立 | 最后两维 `(phase, freq)` |
| 3D 采集 | 每个 `coil` | 最后三维 `(slice, phase, freq)` |

区别在于 slice 方向有没有相位编码：2D 逐层采集时 slice 维不参与 IFFT，3D 体积采集时参与。
转换后取幅度，多线圈用平方和开根（RSS）合并。

## 界面与操作

```
+------------------+------------------+------------+
|   K-Space 显示    |     图像显示      |  增强面板   |
+------------------+------------------+            |
+-------------------------------------+------------+
|           切片 / 视角导航（底部）                   |
+--------------------------------------------------+
```

- **打开**：`Ctrl+O`，或把文件拖进窗口
- **保存当前图**：`Ctrl+S`（JPG / PNG）
- **翻层**：方向键、底部滑块、鼠标滚轮、点击图像
- **切视角**：底部的横截面 / 矢状面 / 冠状面标签页
- **缩放**：`Ctrl+滚轮`、`Ctrl++` / `Ctrl+-` / `Ctrl+0`
- **增强**：右侧面板，先在顶部选 `K-Space` 或 `Image`，两套参数各自独立保存
  - 对比度 `0.1x–5.0x`、亮度 `-1.0–+1.0`
  - **Log 变换**：看 k-space 时几乎必开，否则动态范围太大会只看到中心一个亮点
  - 任意角度旋转、90° 快捷键、缩放、水平/垂直翻转
- **重置当前目标**：`Ctrl+R`

## 大文件与内存

`.h5` 走惰性读取：打开 778 MB 的 k-space 数据集时不会把它整个读进内存。

| 场景 | 峰值内存 |
|---|---|
| 打开 + 轴向（默认视角）速览 | ~280 MB |
| 首次切到矢状面 / 冠状面 | 需要一次性构建体数据，内存上升、耗时数秒 |
| 之后继续切换矢状面 / 冠状面 | 即时 |

`.npy` / `.mat` 由 NumPy / SciPy 整体读取，不享受该优化。

## 测试与开发

```bash
python -m pytest -q            # 完整测试套件（离屏 Qt）
python test_core.py            # 旧版核心冒烟测试（保留）
python verify.py               # 旧版端到端验证（保留）
ruff check . && black --check .
```

无显示器环境请设置 `QT_QPA_PLATFORM=offscreen`。CI 见 `.github/workflows/test.yml`。

## 项目结构

```
src/
├── main.py                  # 入口（QApplication 引导）
├── main_window.py           # 主窗口：布局 / 菜单 / 信号连线（薄协调层）
├── app/                     # 应用层：把 core 和 ui 接起来
│   ├── file_loader.py       #   文件对话框与加载（.npy / .h5 / .mat）
│   ├── display.py           #   视角提取、RSS 合并、渲染、显示缓存
│   ├── enhancement.py       #   双处理器与增强参数同步
│   └── lazy.py              #   大 HDF5 的惰性只读代理
├── core/                    # 纯计算层，不依赖 Qt
│   ├── views.py             #   ★ 视角 / 索引语义的唯一权威
│   ├── mri_data.py          #   加载、形状归一化、惰性读取
│   ├── kspace_converter.py  #   2D / 3D IFFT
│   └── image_processor.py   #   对比度 / 亮度 / Log / 旋转 / 缩放 / 翻转
└── ui/                      # 纯界面层
    ├── image_canvas.py      #   图像画布
    ├── enhancement_panel.py #   增强面板
    └── slice_navigator.py   #   切片 / 视角导航
```

分层原则：`core` 不依赖 Qt（可脱离 GUI 单测），`ui` 不含数值逻辑，`app` 负责装配。

## 技术栈

PyQt5、NumPy、SciPy（`ndimage` 旋转缩放、`.mat` 读取）、h5py、Pillow。

## 已知限制

- 视角语义固定为「axial 固定 S、sagittal 固定 W、coronal 固定 H」，不做任意斜位重建。
- k-space 的自动类型检测只是启发式，GUI 里以你的选择为准。
- HDF5 只取单个数据集，不解析 ISMRMRD 头部。
- `.npy` / `.mat` 不享受惰性加载。
- 不做定量分析、不做配准、不写 DICOM。

## 许可证

本项目仅供学习与研究使用。
