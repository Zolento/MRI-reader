# MRI Reader 发布指南

本文档说明如何将MRI Reader打包成可执行文件并发布到GitHub Release。

## 目录

1. [本地打包](#1-本地打包)
2. [使用GitHub Actions自动发布](#2-使用github-actions自动发布)
3. [手动发布](#3-手动发布)
4. [发布清单](#4-发布清单)

---

## 1. 本地打包

### Windows 环境

```powershell
# 1. 安装依赖
uv sync
uv pip install pyinstaller

# 2. 执行打包
pyinstaller build.spec --clean --noconfirm

# 3. 生成的文件在 dist/MRI-Reader/ 目录
# 包含 MRI-Reader.exe 及所有依赖

# 4. 压缩为zip
Compress-Archive -Path dist\MRI-Reader -DestinationPath MRI-Reader-Windows.zip
```

### Linux 环境

```bash
# 1. 安装依赖
uv sync
uv pip install pyinstaller

# 2. 执行打包 (使用提供的脚本)
chmod +x build.sh
./build.sh

# 3. 或手动打包
pyinstaller build.spec --clean --noconfirm

# 4. 压缩为tar.gz
cd dist
tar -czf MRI-Reader-Linux.tar.gz MRI-Reader/
```

### macOS 环境

```bash
# 1. 安装依赖
uv sync
uv pip install pyinstaller

# 2. 执行打包
pyinstaller build.spec --clean --noconfirm

# 3. 压缩为zip
cd dist
zip -r MRI-Reader-macOS.zip MRI-Reader/
```

## 2. 使用GitHub Actions自动发布

### 设置步骤

#### 步骤1: 创建GitHub标签

```bash
# 在本地创建版本标签
git tag -a v0.1.0 -m "Release v0.1.0 - Initial release"

# 推送标签到GitHub
git push origin v0.1.0
```

#### 步骤2: 自动触发构建

推送标签后,GitHub Actions会自动:
1. 在Windows、Linux、macOS三个平台上构建可执行文件
2. 打包为zip/tar.gz格式
3. 创建GitHub Release并上传构建产物

#### 步骤3: 查看Release

访问: `https://github.com/你的用户名/mri-reader/releases`

### 手动触发工作流

1. 进入GitHub仓库页面
2. 点击 **Actions** 标签
3. 选择 **Build and Release** 工作流
4. 点击 **Run workflow**
5. 输入版本号 (如 `v0.1.0`)
6. 点击 **Run workflow** 按钮

## 3. 手动发布

### 步骤1: 准备发布内容

```bash
# 1. 更新版本号
# 编辑以下文件中的版本号:
# - pyproject.toml (version = "0.1.0")
# - src/main.py (app.setApplicationVersion("0.1.0"))
# - README.md
# - RELEASE_NOTES.md

# 2. 提交更改
git add .
git commit -m "Bump version to v0.1.0"

# 3. 创建标签
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

### 步骤2: 在各平台构建

按照[本地打包](#1-本地打包)说明,在三个平台上分别构建。

### 步骤3: 创建GitHub Release

#### 方法A: 使用GitHub Web界面

1. 访问: `https://github.com/你的用户名/mri-reader/releases/new`
2. 选择标签: 选择 `v0.1.0`
3. 填写Release标题: `MRI Reader v0.1.0`
4. 粘贴发布说明: 复制 `RELEASE_NOTES.md` 的内容
5. 上传文件: 拖拽上传构建好的压缩包
   - `MRI-Reader-Windows.zip`
   - `MRI-Reader-Linux.tar.gz`
   - `MRI-Reader-macOS.zip`
6. 点击 **Publish release**

#### 方法B: 使用GitHub CLI

```bash
# 安装GitHub CLI (如未安装)
# Windows: winget install GitHub.cli
# Linux: sudo apt install gh
# macOS: brew install gh

# 登录
gh auth login

# 创建Release
gh release create v0.1.0 \
  --title "MRI Reader v0.1.0" \
  --notes-file RELEASE_NOTES.md \
  MRI-Reader-Windows.zip \
  MRI-Reader-Linux.tar.gz \
  MRI-Reader-macOS.zip
```

## 4. 发布清单

### 发布前检查

- [ ] 所有功能测试通过
- [ ] 更新版本号 (pyproject.toml, main.py)
- [ ] 更新CHANGELOG.md
- [ ] 更新RELEASE_NOTES.md
- [ ] 在各个平台测试打包
- [ ] 测试生成的exe文件能否正常运行
- [ ] 检查文件大小是否合理
- [ ] 确认README.md是最新的

### 发布后检查

- [ ] Release页面可以正常访问
- [ ] 所有下载链接有效
- [ ] 发布说明格式正确
- [ ] 通知用户新版本发布

## 5. 版本号规范

遵循语义化版本 (Semantic Versioning):

- **主版本号**: 不兼容的API修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

示例:
- `v0.1.0` - 初始版本
- `v0.2.0` - 添加新功能
- `v0.2.1` - 修复bug
- `v1.0.0` - 稳定版本

## 6. 常见问题

### Q: 打包后的exe文件太大?

A: 正常现象。Python打包会包含完整的Python运行时和所有依赖。可以使用以下方法优化:

```bash
# 使用UPX压缩 (已在build.spec中启用)
uv pip install upx

# 排除不需要的模块
# 在build.spec的excludes列表中添加
```

### Q: 运行时被杀毒软件拦截?

A: PyInstaller打包的程序可能会被误报。解决方法:

1. 添加数字签名 (Windows)
2. 向杀毒软件厂商提交误报
3. 提示用户添加信任

### Q: 如何减小打包体积?

A: 使用以下方法:

```bash
# 1. 使用虚拟环境,只安装必需依赖
uv sync --no-dev

# 2. 使用--onefile参数 (会增大单个文件大小但更方便分发)
pyinstaller build.spec --onefile

# 3. 排除不必要的模块
# 在build.spec中配置excludes
```

### Q: 缺少系统库错误?

A: Linux上可能缺少某些系统库。确保目标系统安装了:

```bash
# Ubuntu/Debian
sudo apt install libxcb-xinerama0 libxcb-cursor0

# Fedora
sudo dnf install libxcb
```

## 7. 完整发布流程示例

```bash
# 1. 准备发布
git checkout main
git pull

# 2. 更新版本号 (手动编辑或使用工具)
# pyproject.toml: version = "0.2.0"
# src/main.py: app.setApplicationVersion("0.2.0")

# 3. 提交更改
git add pyproject.toml src/main.py RELEASE_NOTES.md
git commit -m "Bump version to v0.2.0"

# 4. 创建并推送标签
git tag -a v0.2.0 -m "Release v0.2.0 - Add new features"
git push origin main
git push origin v0.2.0

# 5. 等待GitHub Actions完成 (约5-10分钟)
# 查看: https://github.com/你的用户名/mri-reader/actions

# 6. 检查Release
# 访问: https://github.com/你的用户名/mri-reader/releases

# 7. 下载测试各个版本的可执行文件

# 8. 发布完成! 🎉
```

## 8. 额外建议

1. **预发布版本**: 对于测试版,使用 `v0.1.0-beta.1` 这样的标签,并在Release中标记为预发布

2. **自动更新检查**: 考虑在程序中添加版本检查功能,提示用户更新

3. **提供多种格式**: 
   - Windows: `.exe` (onefile) 或文件夹
   - Linux: `.AppImage` (更便于分发)
   - macOS: `.dmg` 或 `.app`

4. **发布渠道**: 除了GitHub Release,还可以考虑:
   - PyPI (pip install)
   - Microsoft Store
   - Snap/Flatpak (Linux)
   - Homebrew (macOS)

---

**最后更新**: 2026-04-12
