# MRI Reader 发布说明

> 本文件同时作为 GitHub Release 的正文模板（见 `.github/workflows/release.yml`）。
> 发版时请把「本次变更」一节替换为新版本的内容。

## MRI Reader v0.3.0 — 正确性修复 + 大文件速览 + 测试与工程化

这个版本围绕一个目标：**在深度学习的数据管线里更快、更可靠地速览 MRI 数据**。
修掉了 20 个缺陷（含 4 个会静默给出错误结果的正确性问题），把 778 MB 数据的峰值内存
从 3.0 GB 降到约 220 MB，并补上了此前完全缺失的测试与 CI。

### 🔴 正确性修复（会给出错误结果的）

- **矢状面 / 冠状面的轴用反了**：矢状面错误索引行（H）轴、冠状面错误索引列（W）轴，
  平面形状与切片范围都错。现统一为横截面固定 S、矢状面固定 W、冠状面固定 H。
- **`.mat` 单例轴被静默抹掉**：`(1,5,7,11)` 选择 `(Coil,Slice,H,W)` 会被读成 `(5,1,7,11)`
  —— 5 个切片变成 5 个线圈。现在保留 MATLAB 的真实维度，让显式维度选择生效。
- **斜位视角下画布切片范围失效**：矢状面/冠状面下鼠标滚轮与点击无法越过 `S-1`
  （真实数据上只能到 15，而矢状面实际有 396 个索引）。
- **换文件时增强参数被污染**：目标停在 K-Space 时，旧的 k-space 参数会被写入刚重置的
  图像处理器，用户会发现图像参数莫名其妙变了。

### 🐛 其他修复

- `Ctrl+滚轮` 缩放此前完全无效（绘制时忽略了缩放倍数）。
- 滚轮在滑块 / 方向键之后会跳到错误切片。
- 含 Group 的 HDF5 在选择文件后、确认加载前直接崩溃。
- 0D/1D 数据集或只有 Group 的 HDF5 抛出难懂的 `IndexError`/`AttributeError`；现为清晰的 `ValueError`。
- 仅探测 `.npy` 维度却整包加载：153 MB 文件曾多占 152.9 MB 内存、多花 36 ms；现在只读头部（0.0 MB / 0.1 ms）。
- 尾随单例（如 `(H,W,1)`）的 `.mat` 曾被误读成单列图像。
- 惰性 HDF5 源 `close()` 之后会被静默重新打开（不可追踪的文件句柄）。
- `.mat` 打开流程重复整包解析 3 次；现按 (路径, 大小, mtime) 缓存为 1 次。
- 加载图像数据后左侧 k-space 画布残留上一次的数据。
- 增强面板滑块/数值框重复发信号，导致同一次编辑渲染两次。
- 惰性代理的 `__array__` 不兼容 NumPy 2.x 的 `copy=` 关键字。
- 版本号单一来源（此前 `src/` 内硬编码 0.1.0 与 `pyproject.toml` 冲突）。

### ⚡ 性能

| 指标 | v0.2.0 | v0.3.0 |
|---|---|---|
| 778 MB 脑部 HDF5 峰值内存 | ~3030 MB | **~220 MB**（≈13×） |
| 打开 + 首次渲染 | ~6.2 s | **0.27 s** |
| 首次切到矢状面 / 冠状面 | — | 2.3 s（一次性物化） |
| 之后切换斜位切片 | — | **0.2–1.9 ms** |

`.h5` 改为惰性读取 + 只读代理；轴向速览只读/只转换当前层，斜位首次访问才一次性构建体数据。
数值未变：惰性与 eager 路径逐位一致（已用独立参考实现复核，`maxdiff = 0.0`）。

### 🏗️ 结构

- `MainWindow` 从 1126 行降到 397 行，拆分为 `src/app/`：`file_loader` / `display` / `enhancement` / `lazy`。
- 新增 `src/core/views.py`，作为视角与索引语义的唯一权威（此前 core 与 GUI 各有一份、且互相矛盾）。
- 分层约定：`core` 不依赖 Qt（可脱离 GUI 单测），`ui` 不含数值逻辑，`app` 负责装配。

### 🧪 测试与工程化

- **从 0 个测试到 203 个 pytest 用例**：规范化矩阵、正逆 IFFT 一致性、离屏 GUI 回归、
  数值特征化、惰性内存预算、资源泄漏、各缺陷的回归用例。
- 新增 CI `.github/workflows/test.yml`：Python 3.9 / 3.11 上跑 ruff + black + pytest。
- 新增 `pyproject.toml` 配置：`.[dev]` 可选依赖、pytest / ruff / black 配置、`mri-reader` 控制台入口。
- `README.md` / `README_en.md` / `AGENTS.md` 重写，定位为「DL 工程里用来速览数据的轻量读取器」。

### ⚠️ 已知限制

- 视角语义固定（axial→S、sagittal→W、coronal→H），不做任意斜位重建。
- k-space 自动类型检测只是启发式，以用户在对话框中的选择为准。
- HDF5 只取单个数据集，不解析 ISMRMRD 头部。
- `.npy` / `.mat` 由 NumPy / SciPy 整体读取，不享受惰性加载（`.mat` 因 SciPy 无 header-only 模式）。
- 真实 `W=1` 的单列 3-D 体数据会被读成 2-D —— 与历史行为一致，如需支持需另加显式选项。
- JPG 保存是有损的，需要无损请用 PNG。

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
