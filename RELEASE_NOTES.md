# GitHub Release 发布说明模板

## MRI Reader v0.1.0

### 📥 下载

选择适合您操作系统的版本:

- **Windows**: `MRI-Reader-Windows.zip`
- **Linux**: `MRI-Reader-Linux.tar.gz`
- **macOS**: `MRI-Reader-macOS.zip` (如已构建)

### 🚀 快速开始

#### Windows 用户
1. 下载并解压 `MRI-Reader-Windows.zip`
2. 进入解压后的文件夹
3. 双击运行 `MRI-Reader.exe`

#### Linux 用户
1. 下载并解压: `tar -xzf MRI-Reader-Linux.tar.gz`
2. 进入目录: `cd MRI-Reader`
3. 运行程序: `./MRI-Reader`
4. 如果提示权限问题,执行: `chmod +x MRI-Reader`

#### macOS 用户
1. 下载并解压 `MRI-Reader-macOS.zip`
2. 在终端中运行: `./MRI-Reader`
3. 如果遇到安全提示,请在"系统偏好设置 > 安全性与隐私"中允许运行

### ✨ 新功能

- 智能数据检测:自动识别2D/3D,可选图像/k-space数据类型
- k-space转换:支持2D逐切片IFFT和3D完整IFFT转换
- 多格式支持:读取.npy文件,保存为.jpg/.png格式
- 多视角显示:3D数据支持横截面(Axial)、矢状面(Sagittal)、冠状面(Coronal)
- 图像增强:对比度、亮度、旋转、缩放、翻转等功能
- 3D导航:滑动条、键盘快捷键、鼠标滚轮切换切片

### 📋 系统要求

- **Windows**: Windows 10 或更高版本
- **Linux**: 现代Linux发行版 (Ubuntu 18.04+, Fedora 30+, 等)
- **macOS**: macOS 10.15 或更高版本

### 🐛 已知问题

- 首次运行时可能会被杀毒软件误报,请添加信任
- 某些旧版Linux发行版可能缺少系统库

### 📝 使用说明

详细使用说明请查看 [README.md](README.md)

### 💻 从源码构建

```bash
# 克隆仓库
git clone https://github.com/你的用户名/mri-reader.git
cd mri-reader

# 安装依赖
./setup.sh

# 打包可执行文件
./build.sh
```

### 📄 许可证

本项目仅供学习和研究使用。

### 🙏 致谢

感谢所有贡献者和用户!

---

**完整更新日志**: 查看 [CHANGELOG.md](CHANGELOG.md)
