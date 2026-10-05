# MRI Reader 发布说明

> 本文件同时作为 GitHub Release 的正文模板（见 `.github/workflows/release.yml`）。
> 发版时请把「本次变更」一节替换为新版本的内容。

## 本次变更（未发布）

### 🐛 修复

几何与显示：
- **矢状面 / 冠状面的轴用反了**：矢状面错误地索引了行（H）轴、冠状面错误地索引了列（W）轴，
  导致平面形状与切片范围都错。现在统一为：横截面固定切片轴 S、矢状面固定列轴 W、冠状面固定行轴 H，
  并且视角/索引语义只在 `src/core/views.py` 维护一处。
- **斜位视角下画布切片范围失效**：画布自身的切片范围没有随视角更新，矢状面/冠状面下鼠标滚轮与点击
  无法越过 `S-1`（真实数据上只能到 15，而矢状面实际有 396 个索引）。
- **滚轮在滑块 / 方向键之后跳到错误切片**：画布的 `current_slice` 未与权威切片索引同步。
- **画布缩放无效**：`Ctrl+滚轮` 改变了缩放倍数但绘制时被忽略，画面纹丝不动。
- **QImage 缓冲区生命周期**：绘制前底层 numpy 数组可能已被回收。

状态与交互：
- 换文件时若增强目标停在 K-Space，陈旧的 K-Space 参数会被写入刚重置的图像处理器（对比度 2.0 而非 1.0）。
- 加载图像数据后左侧 k-space 画布会残留上一次的 k-space（脏状态）。
- 增强面板的滑块/数值框会重复发出一次信号，导致同一次编辑渲染两次。

文件读取：
- **`.mat` 单例轴被 `np.squeeze` 压掉导致静默误读**：`(1,5,7,11)` 选了 `(Coil,Slice,H,W)` 会被
  当成 `(5,1,7,11)` —— 5 个切片变成 5 个线圈。现在保留 MATLAB 的真实维度，让用户的显式选择生效。
- **含 Group 的 HDF5 在维度探测阶段崩溃**（`AttributeError`），选完文件还没确认加载就挂。
- **仅探测 `.npy` 维度却整包加载**：153 MB 文件 RSS +152.9 MB、耗时 36 ms；现在只读头部，0.0 MB / 0.1 ms。
- 顶层为 0D/1D 数据集或只有 Group 的 HDF5 抛出 `IndexError`/`AttributeError`；现在统一为清晰的 `ValueError`。
- 惰性 HDF5 源在 `close()` 之后会被静默重新打开（不可追踪的文件句柄）；现在抛出清晰错误。
- `.mat` 打开流程会重复整包解析 3 次；现在按 (路径, 大小, mtime) 缓存，降为 1 次。
- 版本号不一致（`src/` 内硬编码 0.1.0 而 `pyproject.toml` 为 0.2.0）→ 收敛为单一来源 `src/__init__.py`。

### ⚡ 性能

以大文件速览为目标，`.h5` 改为**惰性读取**（778 MB 脑部 k-space 数据集）：

| 指标 | 优化前 | 优化后 |
|---|---|---|
| 峰值内存 | ~3030 MB | **~280 MB**（约 10.8×） |
| 打开 + 首次轴向渲染 | ~6.2 s | **~0.27 s** |

数值未变：惰性路径与 eager 路径的输出逐位一致（已独立复核）。

### 🏗️ 结构

- `MainWindow` 从 1126 行降到 396 行，拆分为 `src/app/`：`file_loader` / `display` / `enhancement` / `lazy`。
- 新增 `src/core/views.py` 作为视角与索引语义的唯一权威。
- 版本号单一来源：`src/__init__.py:__version__`（此前 `src/main.py` 硬编码 0.1.0 与 pyproject 不一致）。

### 🧪 测试与工程化

- 从**零测试**到 **148 个 pytest 用例**（含离屏 GUI 回归、惰性内存预算、数值特征化）。
- 新增 CI：`.github/workflows/test.yml` 在 Python 3.9 / 3.11 上跑 lint + format check + pytest。
- 新增 `pyproject.toml` 配置：`[tool.pytest.ini_options]`、`[tool.ruff]`、`[tool.black]`、`.[dev]` 可选依赖。
- 新增 `mri-reader` 控制台入口。

### ⚠️ 已知限制

- 视角语义固定（axial→S、sagittal→W、coronal→H），不做任意斜位重建。
- k-space 自动类型检测只是启发式，以用户在对话框中的选择为准。
- HDF5 只取单个数据集，不解析 ISMRMRD 头部。
- `.npy` / `.mat` 由 NumPy / SciPy 整体读取，不享受惰性加载。

---

## 📥 下载

选择适合你操作系统的版本：

- **Windows**: `MRI-Reader-Windows.zip`
- **Linux**: `MRI-Reader-Linux.tar.gz`
- **macOS**: `MRI-Reader-macOS.zip`（如已构建）

### 🚀 快速开始

#### Windows 用户
1. 下载并解压 `MRI-Reader-Windows.zip`
2. 进入解压后的文件夹
3. 双击运行 `MRI-Reader.exe`

#### Linux 用户
1. 下载并解压: `tar -xzf MRI-Reader-Linux.tar.gz`
2. 进入目录: `cd MRI-Reader`
3. 运行程序: `./MRI-Reader`
4. 如果提示权限问题，执行: `chmod +x MRI-Reader`

#### macOS 用户
1. 下载并解压 `MRI-Reader-macOS.zip`
2. 在终端中运行: `./MRI-Reader`
3. 如果遇到安全提示，请在「系统偏好设置 > 安全性与隐私」中允许运行

### 📋 系统要求

- **Windows**: Windows 10 或更高版本
- **Linux**: 现代 Linux 发行版（Ubuntu 18.04+、Fedora 30+ 等）
- **macOS**: macOS 10.15 或更高版本

### 🐛 已知问题

- 首次运行时可能会被杀毒软件误报，请添加信任
- 某些旧版 Linux 发行版可能缺少系统库（`libgl1`、`libegl1`、`libxkbcommon-x11-0`）

### 📝 使用说明

详细使用说明请查看 [README.md](README.md)。

### 💻 从源码构建

```bash
git clone https://github.com/你的用户名/mri-reader.git
cd mri-reader

# 安装（含开发工具）
pip install -e ".[dev]"

# 运行
python -m src.main

# 测试
python -m pytest -q

# 打包可执行文件
./build.sh
```

### 📄 许可证

本项目仅供学习和研究使用。

### 🙏 致谢

感谢所有贡献者和用户！
