from __future__ import annotations

import os
import subprocess
import tempfile
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
TS_CONVERSION_TIMEOUT_SECONDS = 1800


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
    input_durations: tuple[float, ...] = ()


def _probe_clip(path: str, source_path: str) -> VideoMeta:
    """Read metadata from an already prepared video file."""
    clip = VideoFileClip(path)
    try:
        return VideoMeta(
            path=source_path,
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


def _convert_ts_to_mp4(input_path: str, output_path: str) -> None:
    """Convert TS to MP4, preferring remuxing before transcoding."""
    remux_command = [
        FFMPEG_RUNTIME_PATH,
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        "-avoid_negative_ts",
        "make_zero",
        output_path,
    ]
    transcode_command = [
        FFMPEG_RUNTIME_PATH,
        "-y",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "+genpts+discardcorrupt",
        "-err_detect",
        "ignore_err",
        "-i",
        input_path,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-avoid_negative_ts",
        "make_zero",
        output_path,
    ]
    run_kwargs = {
        "capture_output": True,
        "text": True,
        "check": False,
        "timeout": TS_CONVERSION_TIMEOUT_SECONDS,
    }
    if os.name == "nt":
        run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    def run_ffmpeg(command: list[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(command, **run_kwargs)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"TS 文件转换超时：{Path(input_path).name}，"
                f"超过 {TS_CONVERSION_TIMEOUT_SECONDS // 60} 分钟"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"无法启动 FFmpeg 转换 TS 文件：{Path(input_path).name}\n{exc}") from exc

    remux_result = run_ffmpeg(remux_command)
    if remux_result.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
        return

    try:
        Path(output_path).unlink(missing_ok=True)
    except OSError:
        pass

    transcode_result = run_ffmpeg(transcode_command)
    if transcode_result.returncode == 0 and Path(output_path).exists() and Path(output_path).stat().st_size > 0:
        return

    details = (
        transcode_result.stderr
        or transcode_result.stdout
        or remux_result.stderr
        or remux_result.stdout
        or "未知 FFmpeg 错误"
    ).strip()
    raise RuntimeError(f"TS 文件转换失败：{Path(input_path).name}\n{details}")


def probe_video(path: str) -> VideoMeta:
    """Read video metadata, preparing TS input in a temporary MP4 first."""
    if Path(path).suffix.lower() != ".ts":
        return _probe_clip(path, path)

    with tempfile.TemporaryDirectory(prefix="video_stitcher_probe_") as temp_dir:
        converted_path = str(Path(temp_dir) / f"{Path(path).stem}_probe.mp4")
        _convert_ts_to_mp4(path, converted_path)
        return _probe_clip(converted_path, path)


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


def _concat_copy_inputs(
    input_paths: list[str],
    output_path: str,
    expected_duration: float,
    on_status: Callable[[str], None],
    on_progress: Callable[[int], None],
) -> bool:
    """Try to concatenate compatible inputs without re-encoding.

    Returns True only when FFmpeg succeeds and creates a non-empty output.
    A False result is intentionally non-fatal so the caller can use MoviePy
    as the compatibility fallback.
    """
    output_parent = Path(output_path).expanduser().resolve().parent
    try:
        output_parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    # Keep the temporary output on the destination volume. Windows cannot
    # atomically replace a file across different drives or file systems.
    with tempfile.TemporaryDirectory(
        prefix="video_stitcher_concat_",
        dir=str(output_parent),
    ) as temp_dir:
        list_path = Path(temp_dir) / "inputs.txt"
        temp_output = Path(temp_dir) / "stitched.mp4"

        def quote_concat_path(path: str) -> str:
            # The concat demuxer uses single-quoted paths and forward slashes.
            normalized = str(Path(path).resolve()).replace("\\", "/")
            return normalized.replace("'", "'\\''")

        list_path.write_text(
            "".join(f"file '{quote_concat_path(path)}'\n" for path in input_paths),
            encoding="utf-8",
        )
        command = [
            FFMPEG_RUNTIME_PATH,
            "-y",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
            "-progress",
            "pipe:1",
            "-nostats",
            str(temp_output),
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        on_status("Trying fast stream-copy concatenation...")
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
        except OSError:
            return False

        stderr_text = ""
        try:
            assert process.stdout is not None
            for line in process.stdout:
                if not line.startswith("out_time_ms="):
                    continue
                try:
                    current_seconds = int(line.split("=", 1)[1]) / 1_000_000
                except ValueError:
                    continue
                if expected_duration > 0:
                    ratio = max(0.0, min(current_seconds / expected_duration, 1.0))
                    on_progress(40 + int(ratio * 55))
            assert process.stderr is not None
            stderr_text = process.stderr.read()
            return_code = process.wait(timeout=TS_CONVERSION_TIMEOUT_SECONDS)
        except (subprocess.TimeoutExpired, OSError):
            process.kill()
            process.wait()
            return False

        if return_code != 0 or not temp_output.exists() or temp_output.stat().st_size == 0:
            if stderr_text:
                on_status("Fast concatenation unavailable; falling back to re-encoding.")
            return False

        try:
            os.replace(temp_output, output_path)
        except OSError:
            return False
        on_progress(95)
        on_status("Fast stream-copy concatenation completed.")
        return True


def stitch_videos(
    input_paths: list[str],
    output_path: str,
    config: StitchConfig,
    on_status: Callable[[str], None],
    on_progress: Callable[[int], None],
) -> None:
    """Join videos, preferring stream copy and falling back to MoviePy."""
    if not input_paths:
        raise ValueError("未选择任何输入视频。")

    prepared_clips = []
    opened_clips = []
    final_clip = None
    with tempfile.TemporaryDirectory(prefix="video_stitcher_") as temp_dir:
        prepared_paths = []
        total = len(input_paths)
        for index, path in enumerate(input_paths, start=1):
            if Path(path).suffix.lower() == ".ts":
                on_status(f"正在转换 TS 片段 {index}/{total}: {Path(path).name}")
                converted_path = str(Path(temp_dir) / f"{index:04d}_{Path(path).stem}.mp4")
                _convert_ts_to_mp4(path, converted_path)
                prepared_paths.append(converted_path)
            else:
                prepared_paths.append(path)
            on_progress(int((index / total) * 15))

        if not config.normalize and all(Path(path).suffix.lower() != ".ts" for path in input_paths):
            expected_duration = sum(config.input_durations)
            if _concat_copy_inputs(
                prepared_paths,
                output_path,
                expected_duration,
                on_status,
                on_progress,
            ):
                on_progress(100)
                on_status("Output completed.")
                return

        try:
            for index, path in enumerate(prepared_paths, start=1):
                on_status(f"正在读取片段 {index}/{total}: {Path(input_paths[index - 1]).name}")
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
                on_progress(15 + int((index / total) * 20))

            on_status("正在合并视频片段...")
            final_clip = concatenate_videoclips(prepared_clips, method="compose")
            logger = _QtProgressLogger(on_progress=on_progress, start=40, span=60)
            final_clip.write_videofile(
                output_path,
            codec="libx264",
            audio_codec="aac",
            audio_fps=config.audio_fps,
            ffmpeg_params=["-ac", str(config.audio_channels)],
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
