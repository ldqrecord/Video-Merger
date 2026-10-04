# Video-Merger

`Video-Merger` 是一个基于 `Python`、`PyQt6` 和 `MoviePy` 开发的 Windows 桌面视频拼接工具，面向“零配置、双击即用”的使用场景。用户可以通过拖拽或点击导入多个视频片段，统一处理不同分辨率和帧率后，一键导出为标准 MP4 视频。

项目内置 FFmpeg 运行时定位逻辑，并支持通过 `PyInstaller` 打包为单文件 `.exe`，适合个人使用、离线分发和后续功能扩展。

## 项目特性

- 支持拖拽添加视频文件
- 支持常见格式：`mp4`、`mov`、`avi`、`mkv`、`flv`
- 支持视频流格式：`ts`，拼接前自动转换为临时 `mp4`
- 支持上移 / 下移调整拼接顺序
- 自动检测视频分辨率和帧率是否一致
- 参数不一致时可选择：
  - 输出为 `1080p 30FPS`
  - 使用第一个视频的参数
  - 自定义输出参数
- 自动进行等比缩放与黑边填充
- 使用后台线程处理拼接任务，避免界面卡死
- 显示实时已耗时和任务完成后的总处理耗时
- 支持打包为独立运行的 Windows `.exe`

## 当前优化状态

以下两项优化已完成代码实现，待后续打包和完整样例验证：

1. **处理耗时反馈**
   - 在 GUI 输出区域显示任务已耗时。
   - 任务完成后显示本次拼接总耗时。
   - 任务失败或取消时保留已耗时信息。

2. **`.ts` 视频自动转换**
   - 将 `.ts` 作为视频格式接收，不处理为 TypeScript 源文件。
   - 拼接前先使用内置 FFmpeg 将 `.ts` 转换为临时 `.mp4`。
   - 转换后的临时文件进入统一的参数检测、标准化和拼接流程。

## 仓库地址

```bash
git clone https://github.com/ldqrecord/Video-Merger.git
cd Video-Merger
```

## 环境要求

- Python `3.10.x`
- 推荐在 Windows 环境下运行和打包

安装依赖：

```powershell
python -m pip install --upgrade pip
python -m pip install PyQt6 moviepy imageio-ffmpeg pyinstaller
```

## 项目结构

```text
Video-Merger/
├─ main.py
├─ video_processing.py
├─ Video_Stitcher.spec
├─ build_exe.ps1
├─ Video_Stitcher_PRD.md
├─ README.md
├─ README_DEV.md
├─ TEST_CASES.md
└─ .gitignore
```

核心文件说明：

- `main.py`：图形界面入口，负责文件列表、参数选择、线程调度和用户交互
- `video_processing.py`：负责视频信息探测、参数标准化、FFmpeg 绑定和拼接输出
- `Video_Stitcher.spec`：PyInstaller 打包配置文件
- `build_exe.ps1`：Windows 下的打包脚本
- `Video_Stitcher_PRD.md`：项目需求文档，后续功能调整和迭代会持续同步更新
- `README_DEV.md`：开发者维护文档
- `TEST_CASES.md`：功能测试案例、测试步骤和实际执行记录

## 本地运行

启动应用：

```powershell
python .\main.py
```

可选检查：

```powershell
python -m py_compile main.py video_processing.py
```

## 开发分支建议

建议本地开发时按功能创建分支，例如：

```bash
git checkout -b dev/ui-optimize
git checkout -b dev/video-processing-fix
git checkout -b dev/build-update
```

推荐流程：

1. 从主分支拉取最新代码
2. 创建本地功能分支
3. 完成功能开发与自测
4. 提交并推送到远程仓库
5. 发起 Pull Request 合并

## 打包为 EXE

项目使用 `PyInstaller` + `.spec` 文件进行打包，并通过 `imageio-ffmpeg` 集成 FFmpeg 二进制资源。

打包命令：

```powershell
python -m PyInstaller --noconfirm --clean .\Video_Stitcher.spec
```

或使用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

打包完成后输出文件位于：

```text
dist\Video_Stitcher.exe
```

## FFmpeg 说明

- 项目不依赖系统手动安装的 FFmpeg
- `video_processing.py` 会在运行时自动定位 `imageio-ffmpeg` 提供的 FFmpeg 路径
- 打包时 `.spec` 文件会将相关资源一起收集到 `.exe` 中

## 基本使用流程

1. 启动程序
2. 拖拽或选择多个视频文件
3. 调整视频顺序
4. 设置输出文件名
5. 点击开始拼接
6. 如果列表中包含 `.ts` 文件，先自动转换为临时 `.mp4`
7. 如检测到参数不一致，选择输出方案
8. 等待处理完成并查看处理耗时

## 说明

- 当前项目主要面向 Windows 桌面环境
- 如果打包时出现 `Spec file not found`，请确认当前终端位于仓库根目录
- `Video_Stitcher_PRD.md` 是当前项目的需求文档，后续如果业务需求、功能范围或交互方案发生变化，会优先在该文档中更新
- 更详细的维护规范和开发说明请查看 `README_DEV.md`
