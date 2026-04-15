# README_DEV.md
# Video-Merger
Video Stitcher 是一个基于 Python + PyQt6 的桌面视频拼接工具，面向“零配置、双击即用”的 Windows 使用场景。用户可以通过拖拽导入多种格式视频（MP4/MOV/AVI/MKV/FLV），在可视化列表中调整顺序后一键合并输出。项目内置智能参数检测：当分辨率或帧率不一致时，会提示差异并支持按 1080p30、首视频参数或自定义参数统一转码，自动完成等比缩放与黑边填充，最终输出标准 MP4 文件。核心处理在后台线程执行，保证拼接过程中界面不卡顿；同时通过 PyInstaller onefile 打包并集成 FFmpeg（imageio-ffmpeg），实现无额外环境依赖的分发与运行。

## 1. 项目结构说明

```text
codex/
├─ main.py                  # GUI 主入口（PyQt6），负责界面交互、文件列表管理、参数选择、启动后台线程
├─ video_processing.py      # 视频处理核心模块：探测元数据、参数标准化、拼接导出、FFmpeg 运行时配置
├─ Video_Stitcher.spec      # PyInstaller 打包配置（onefile + noconsole + 依赖收集）
├─ build_exe.ps1            # Windows 打包脚本（调用 PyInstaller）
├─ Video_Stitcher_PRD.md    # 需求文档
├─ dist/                    # 打包输出目录（生成后出现）
├─ build/                   # 打包中间产物目录（生成后出现）
└─ __pycache__/             # Python 缓存目录（自动生成）
```

---

## 2. 环境搭建指南

### Python 版本要求
- 推荐：`Python 3.10.x`
- 已验证示例：`Python 3.10.6`

### 安装依赖
在项目根目录执行：

```powershell
python -m pip install --upgrade pip
python -m pip install PyQt6 moviepy imageio-ffmpeg pyinstaller
```

> 说明：`moviepy` 会带入其运行所需的部分依赖（如 `proglog` 等）。

### 快速验证
```powershell
python -m PyInstaller --version
python -m py_compile main.py video_processing.py
```

---

## 3. 核心逻辑解析

### 3.1 智能参数检测（`main.py` + `video_processing.py`）
- `probe_video(path)` 读取每个视频的：
  - 分辨率（`width`, `height`）
  - 帧率（`fps`）
  - 时长（`duration`）
- GUI 层在开始拼接前做一致性判断：
  - 若分辨率/FPS 一致：直接按原参数拼接（`normalize=False`）
  - 若不一致：弹出参数选择对话框（1080p30 / 第一个视频参数 / 自定义）
- 处理层按目标参数标准化：
  - 等比缩放
  - 黑边填充（Padding）到目标分辨率
  - 必要时统一 FPS
  - 输出 MP4（H.264 + AAC）

### 3.2 多线程拼接（`QThread`）
- `StitchWorker(QThread)` 在后台执行 `stitch_videos(...)`
- 主线程仅负责 GUI 渲染和用户交互
- 通过信号槽回传状态：
  - `progress_changed`：更新进度条
  - `status_changed`：更新状态文案
  - `failed`：错误弹窗
  - `completed`：完成提示
- 目的：避免拼接时界面卡死，提高可用性

---

## 4. 打包指南（.exe）

### 4.1 FFmpeg 静态资源策略
项目通过 `imageio_ffmpeg` 提供 FFmpeg 二进制，并在运行时主动绑定：
- `video_processing.py` 中设置：
  - `IMAGEIO_FFMPEG_EXE` 环境变量
  - `moviepy.config.change_settings({"FFMPEG_BINARY": ...})`
- 优先使用 `get_ffmpeg_executable()`，旧版本自动回退 `get_ffmpeg_exe()`

### 4.2 打包命令（推荐）
在项目根目录执行：

```powershell
python -m PyInstaller --noconfirm --clean .\Video_Stitcher.spec
```

或使用脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

### 4.3 打包模式与结果
- 模式：`--onefile`（单文件） + `--noconsole`（无控制台窗口）
- 输出：`dist\Video_Stitcher.exe`

### 4.4 常见问题
- 报错 `Spec file not found`：
  - 原因：当前目录不对
  - 解决：先 `cd` 到项目根目录再执行命令

---

## 5. 维护规范

### 5.1 代码修改规范（强制）
后续任何功能变更必须同步完成以下两项：
1. 更新相关函数的 Docstring（参数、返回值、异常、行为说明）
2. 在本文件“更新日志”中追加变更记录

### 5.2 建议提交规范
- 提交信息建议格式：
  - `feat: ...` 新功能
  - `fix: ...` 缺陷修复
  - `refactor: ...` 重构
  - `docs: ...` 文档更新
  - `build: ...` 打包/构建调整

### 5.3 回归检查清单
每次改动后至少执行：
```powershell
python -m py_compile main.py video_processing.py
```
涉及打包链路时额外执行：
```powershell
python -m PyInstaller --noconfirm --clean .\Video_Stitcher.spec
```

---

## 6. 更新日志

- `2026-04-15`
  - 初始化开发者维护文档 `README_DEV.md`
  - 覆盖项目结构、环境搭建、核心逻辑、打包流程、维护规范
