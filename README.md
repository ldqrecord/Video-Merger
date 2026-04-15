# Video-Merger
Video Stitcher 是一个基于 Python + PyQt6 的桌面视频拼接工具，面向“零配置、双击即用”的 Windows 使用场景。用户可以通过拖拽导入多种格式视频（MP4/MOV/AVI/MKV/FLV），在可视化列表中调整顺序后一键合并输出。项目内置智能参数检测：当分辨率或帧率不一致时，会提示差异并支持按 1080p30、首视频参数或自定义参数统一转码，自动完成等比缩放与黑边填充，最终输出标准 MP4 文件。核心处理在后台线程执行，保证拼接过程中界面不卡顿；同时通过 PyInstaller onefile 打包并集成 FFmpeg（imageio-ffmpeg），实现无额外环境依赖的分发与运行。
