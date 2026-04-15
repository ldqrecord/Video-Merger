from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from moviepy.config import change_settings
from moviepy.editor import VideoFileClip, concatenate_videoclips
from proglog import ProgressBarLogger

try:
    from imageio_ffmpeg import get_ffmpeg_executable as _get_ffmpeg_path
except ImportError:
    # Compatible with older imageio-ffmpeg releases.
    from imageio_ffmpeg import get_ffmpeg_exe as _get_ffmpeg_path


def _configure_ffmpeg_runtime() -> str:
    """Point MoviePy to the bundled imageio-ffmpeg binary."""
    ffmpeg_path = _get_ffmpeg_path()
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    change_settings({"FFMPEG_BINARY": ffmpeg_path})
    return ffmpeg_path


FFMPEG_RUNTIME_PATH = _configure_ffmpeg_runtime()


@dataclass
class VideoMeta:
    path: str
    duration: float
    width: int
    height: int
    fps: float


@dataclass
class StitchConfig:
    target_width: int
    target_height: int
    target_fps: float
    normalize: bool
    audio_fps: int = 44100
    audio_channels: int = 2


def probe_video(path: str) -> VideoMeta:
    clip = VideoFileClip(path)
    try:
        return VideoMeta(
            path=path,
            duration=float(clip.duration or 0.0),
            width=int(clip.w),
            height=int(clip.h),
            fps=float(clip.fps or 30.0),
        )
    finally:
        clip.close()


def format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class _QtProgressLogger(ProgressBarLogger):
    def __init__(
        self,
        on_progress: Callable[[int], None],
        start: int = 40,
        span: int = 60,
    ) -> None:
        super().__init__()
        self._on_progress = on_progress
        self._start = start
        self._span = span

    def bars_callback(self, bar, attr, value, old_value=None):
        super().bars_callback(bar, attr, value, old_value)
        if bar != "t" or attr != "index":
            return
        total = self.bars.get("t", {}).get("total", 0)
        if not total:
            return
        ratio = max(0.0, min(float(value) / float(total), 1.0))
        progress = self._start + int(ratio * self._span)
        self._on_progress(progress)


def stitch_videos(
    input_paths: list[str],
    output_path: str,
    config: StitchConfig,
    on_status: Callable[[str], None],
    on_progress: Callable[[int], None],
) -> None:
    if not input_paths:
        raise ValueError("未选择任何输入视频。")

    prepared_clips = []
    opened_clips = []
    final_clip = None
    try:
        total = len(input_paths)
        for index, path in enumerate(input_paths, start=1):
            on_status(f"正在读取片段 {index}/{total}: {Path(path).name}")
            base_clip = VideoFileClip(path)
            opened_clips.append(base_clip)
            work_clip = base_clip

            if config.normalize:
                src_w, src_h = int(base_clip.w), int(base_clip.h)
                if src_w != config.target_width or src_h != config.target_height:
                    scale = min(config.target_width / src_w, config.target_height / src_h)
                    resized_w = max(1, int(src_w * scale))
                    resized_h = max(1, int(src_h * scale))
                    work_clip = work_clip.resize(newsize=(resized_w, resized_h))
                    work_clip = work_clip.on_color(
                        size=(config.target_width, config.target_height),
                        color=(0, 0, 0),
                        pos=("center", "center"),
                    )
                if abs(float(base_clip.fps or 0) - config.target_fps) > 0.01:
                    work_clip = work_clip.set_fps(config.target_fps)

            prepared_clips.append(work_clip)
            on_progress(int((index / total) * 35))

        on_status("正在合并视频片段...")
        final_clip = concatenate_videoclips(prepared_clips, method="compose")
        logger = _QtProgressLogger(on_progress=on_progress, start=40, span=60)
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            audio_fps=config.audio_fps,
            fps=config.target_fps,
            threads=4,
            logger=logger,
        )
        on_progress(100)
        on_status("输出完成。")
    finally:
        if final_clip is not None:
            final_clip.close()
        for clip in prepared_clips:
            try:
                clip.close()
            except Exception:
                pass
        for clip in opened_clips:
            try:
                clip.close()
            except Exception:
                pass
