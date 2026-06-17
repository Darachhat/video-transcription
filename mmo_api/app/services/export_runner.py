"""
Burn editor subtitle clips into the dubbed video using FFmpeg.
Runs as a FastAPI background task — updates EXPORT_MODEL in the DB.
"""
import base64
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_MMO_TOOL_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MMO_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_MMO_TOOL_ROOT))

from dotenv import load_dotenv
load_dotenv(_MMO_TOOL_ROOT / ".env")

from app.core.system.log import logger

OUTPUT_DIR = str(_MMO_TOOL_ROOT / "output")
TEMP_DIR   = str(_MMO_TOOL_ROOT / "temp_assets")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_to_ass(hex_color: str, alpha: float = 1.0) -> str:
    """Convert #RRGGBB + alpha (0–1) to ASS &HAABBGGRR colour."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int((1.0 - min(max(alpha, 0.0), 1.0)) * 255)
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"


def _fmt_srt_time(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms  = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _fmt_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format H:MM:SS.cc (centiseconds)."""
    cs = max(0, int(round(seconds * 100)))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs  = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def _create_srt(clips: list[dict], export_id: str) -> str:
    srt_path = Path(TEMP_DIR) / f"export_{export_id}.srt"
    srt_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    idx = 1
    for clip in sorted(clips, key=lambda c: c.get("start", 0)):
        text = str(clip.get("text", "")).strip()
        if not text:
            continue
        start = float(clip.get("start", 0))
        end   = float(clip.get("end", start + 0.5))
        if end <= start:
            end = start + 0.5
        lines += [str(idx), f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}", text, ""]
        idx += 1

    srt_path.write_text("\n".join(lines), encoding="utf-8")
    return str(srt_path)


def _create_ass_file(
    clips: list[dict],
    export_id: str,
    video_w: int,
    video_h: int,
) -> str:
    """
    Generate an ASS subtitle file that matches the canvas preview exactly.

    Why ASS instead of SRT+force_style:
    - SRT force_style is global; ASS supports per-event override tags.
    - Setting PlayResX/Y = video dimensions makes 1 ASS unit = 1 video pixel,
      so font sizes and positions map 1-to-1 with the canvas coordinate system.
    - The canvas renders fontSize * (H/480) px; we emit fontSize * video_h/480
      as the ASS FontSize, which produces the same visual size in the output.
    - positionY% from top in canvas → MarginV = (1-positionY/100) * video_h
      from the bottom edge for bottom-anchored text.
    """
    # --- Script header -------------------------------------------------------
    margin_lr = max(1, round(0.06 * video_w))  # 6 % left / right — matches canvas

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_w}\n"
        f"PlayResY: {video_h}\n"
        "ScaledBorderAndShadow: yes\n"
        "WrapStyle: 1\n"  # smart word-wrap
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # Default style (values overridden per-event via override tags)
        f"Style: Default,Leelawadee UI,{round(28 * video_h / 480)},"
        "&H00FFFFFF,&H000000FF,&H00000000,&H99000000,"
        "0,0,0,0,100,100,0,0,4,2,0,2,"
        f"{margin_lr},{margin_lr},30,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    # --- Per-clip dialogue lines ---------------------------------------------
    events: list[str] = []
    for clip in sorted(clips, key=lambda c: float(c.get("start", 0))):
        text = str(clip.get("text", "")).strip()
        if not text:
            continue

        start_t = float(clip.get("start", 0))
        end_t   = float(clip.get("end", start_t + 0.5))
        if end_t <= start_t:
            end_t = start_t + 0.5

        s = clip.get("style", {})

        # Font size: canvas renders at  raw_size * (canvas_h / 480).
        # With PlayResY = video_h, the ASS size = raw_size * (video_h / 480)
        # → same relative size as in the preview regardless of preview resolution.
        raw_fs   = int(s.get("fontSize", 28))
        font_size = max(1, round(raw_fs * video_h / 480))

        font_name  = str(s.get("fontFamily", "Leelawadee UI")).replace(",", "").replace("{", "").replace("}", "")
        bold       = 1 if s.get("bold")      else 0
        italic     = 1 if s.get("italic")    else 0
        underline  = 1 if s.get("underline") else 0
        outline_w  = max(0, round(float(s.get("outlineWidth", 2))))

        primary_c = _hex_to_ass(str(s.get("color",        "#ffffff")), 1.0)
        outline_c = _hex_to_ass(str(s.get("outlineColor", "#000000")), 1.0)
        back_op   = min(1.0, max(0.0, float(s.get("bgOpacity", 0.65))))
        back_c    = _hex_to_ass(str(s.get("bgColor", "#000000")), back_op)

        # Alignment: bottom-left=1, bottom-center=2, bottom-right=3 (ASS numpad)
        align_map = {"left": 1, "center": 2, "right": 3}
        alignment = align_map.get(str(s.get("align", "center")), 2)

        # Vertical position:
        # canvas baseline is at positionY% from the top.
        # For bottom-anchored ASS text (an 1/2/3), MarginV is the distance
        # from the BOTTOM of the frame to the bottom of the text block.
        # ∴ margin_v = (1 - positionY/100) × video_h
        pos_y    = float(s.get("positionY", 88))
        margin_v = max(0, round((1.0 - pos_y / 100.0) * video_h))

        # BorderStyle=4 → opaque background box (matches canvas bgOpacity render)
        border_style = 4 if back_op > 0 else 1

        # Build per-event style override tags
        override = (
            f"{{\\an{alignment}"
            f"\\fn{font_name}"
            f"\\fs{font_size}"
            f"\\c{primary_c}"
            f"\\3c{outline_c}"
            f"\\4c{back_c}"
            f"\\b{bold}"
            f"\\i{italic}"
            f"\\u{underline}"
            f"\\bord{outline_w}"
            f"\\shad0"
            f"\\be1"
            f"\\xbord{outline_w}"
            f"\\ybord{outline_w}"
            f"\\1a&H00&"
            f"\\3a&H00&"
            f"\\bs{border_style}"
            f"}}"
        )

        ass_text  = text.replace("\n", "\\N")
        start_str = _fmt_ass_time(start_t)
        end_str   = _fmt_ass_time(end_t)

        events.append(
            f"Dialogue: 0,{start_str},{end_str},Default,,"
            f"{margin_lr},{margin_lr},{margin_v},,"
            f"{override}{ass_text}"
        )

    out_path = Path(TEMP_DIR) / f"export_{export_id}.ass"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + "\n".join(events), encoding="utf-8-sig")
    return str(out_path)


def _style_to_force_style(style: dict, video_height: int = 480) -> str:
    """Map editor SubtitleStyle → FFmpeg subtitles filter force_style string."""
    font     = style.get("fontFamily", "Leelawadee UI").replace("'", r"\'")
    size     = int(style.get("fontSize", 28))
    color    = str(style.get("color", "#ffffff"))
    bg_col   = str(style.get("bgColor", "#000000"))
    bg_op    = float(style.get("bgOpacity", 0.65))
    bold     = 1 if style.get("bold") else 0
    italic   = 1 if style.get("italic") else 0
    underline= 1 if style.get("underline") else 0
    align_s  = style.get("align", "center")
    out_col  = str(style.get("outlineColor", "#000000"))
    out_w    = max(0, int(style.get("outlineWidth", 2)))
    pos_y    = int(style.get("positionY", 88))

    # ASS alignment numpad: 1=BL 2=BC 3=BR  4=ML 5=MC 6=MR  7=TL 8=TC 9=TR
    alignment = {"left": 1, "center": 2, "right": 3}.get(align_s, 2)
    # MarginV: distance from bottom edge in px
    margin_v  = max(5, int((1.0 - pos_y / 100.0) * video_height * 0.6))

    primary  = _hex_to_ass(color,   alpha=1.0)
    back     = _hex_to_ass(bg_col,  alpha=bg_op)
    outline  = _hex_to_ass(out_col, alpha=1.0)

    return (
        f"FontName={font},"
        f"FontSize={size},"
        f"PrimaryColour={primary},"
        f"BackColour={back},"
        f"OutlineColour={outline},"
        f"Bold={bold},"
        f"Italic={italic},"
        f"Underline={underline},"
        f"Alignment={alignment},"
        f"MarginV={margin_v},"
        f"BorderStyle=4,"   # opaque background box
        f"Outline={out_w},"
        f"Shadow=0"
    )


def _get_video_height(video_path: str) -> int:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=height", "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10,
        )
        return int(r.stdout.strip()) or 480
    except Exception:
        return 480


def _escape_subtitle_path(srt_path: str) -> str:
    p = Path(srt_path).resolve().as_posix()
    p = p.replace(":", r"\:")
    p = p.replace("'", r"\'")
    return p


def _save_base64_image(data_url: str, export_id: str, idx: int) -> str:
    """Decode a base64 data URL and write it to a temp file. Returns the path."""
    try:
        header, b64 = data_url.split(",", 1)
    except ValueError:
        header, b64 = "data:image/png;base64", data_url

    ext = "png"
    for fmt in ("jpeg", "jpg", "gif", "webp", "png"):
        if fmt in header:
            ext = "jpg" if fmt == "jpeg" else fmt
            break

    path = Path(TEMP_DIR) / f"export_{export_id}_img{idx}.{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(b64))
    return str(path)


def _get_video_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the video via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             video_path],
            capture_output=True, text=True, timeout=10,
        )
        parts = r.stdout.strip().split(",")
        return int(parts[0]), int(parts[1])
    except Exception:
        return 1280, 720


def _build_image_filter_chain(
    overlays: list[dict],
    img_paths: list[str],
    video_w: int,
    video_h: int,
) -> tuple[list[str], str]:
    """
    Build filter_complex parts that composite image overlays onto the video.
    Returns (filter_parts, last_video_label).
    The caller chains the last_video_label into the subtitle filter (if any).
    """
    parts: list[str] = []
    current = "0:v"         # the evolving video stream label

    for i, (ov, img_path) in enumerate(zip(overlays, img_paths)):
        img_idx   = i + 1   # FFmpeg input index (0 = source video)
        img_w_px  = max(1, int(ov["width"] / 100 * video_w))
        x_px      = int(ov["x"]       / 100 * video_w)
        y_px      = int(ov["y"]       / 100 * video_h)
        alpha     = min(1.0, max(0.0, float(ov.get("opacity", 1.0))))

        scaled    = f"imgsc{i}"
        overlaid  = f"vidov{i}"

        # Scale image to target width (maintain aspect ratio), apply opacity
        parts.append(
            f"[{img_idx}:v]scale={img_w_px}:-1,"
            f"format=rgba,"
            f"colorchannelmixer=aa={alpha:.3f}"
            f"[{scaled}]"
        )
        # Composite onto current video stream
        parts.append(
            f"[{current}][{scaled}]overlay={x_px}:{y_px}[{overlaid}]"
        )
        current = overlaid

    return parts, current


def _get_video_duration(video_path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(r.stdout.strip()) or 0.0
    except Exception:
        return 0.0


def _build_trim_args(
    trim_start: float, trim_end: float | None
) -> dict[str, list[str]]:
    """Split FFmpeg trim args into pre-input (seek) and post-input (duration)."""
    pre: list[str] = []
    post: list[str] = []
    if trim_start > 0:
        pre = ["-ss", f"{trim_start:.6f}"]
    if trim_end is not None:
        post = ["-t", f"{(trim_end - trim_start):.6f}"]
    return {"pre": pre, "post": post}


# ── Main runner ───────────────────────────────────────────────────────────────────────
def run_export_job(
    export_id: str,
    job_id: str,
    clips_json: str,
    trim_start: float = 0.0,
    trim_end: float | None = None,
    image_overlays_json: str = "[]",
) -> None:
    """Background task: composite images + subtitles + optional trim."""
    from app.core.system.db import getStaticSession
    from app.models.export_model import EXPORT_MODEL
    from app.models.job_model import JOB_MODEL

    session = getStaticSession()
    export: EXPORT_MODEL | None = None
    srt_path: str | None = None
    seg_wav_paths: list[str] = []
    composite_audio_path: str | None = None

    try:
        export = session.query(EXPORT_MODEL).filter(EXPORT_MODEL.id == export_id).first()
        job    = session.query(JOB_MODEL).filter(JOB_MODEL.id == job_id).first()

        if not export:
            logger.error(f"[Export {export_id}] record not found")
            return

        if not job or not job.output_path or not Path(job.output_path).exists():
            raise RuntimeError(
                "Source dubbed video not found on disk. "
                "Ensure the dubbing job completed successfully."
            )

        export.status     = "PROCESSING"
        export.updated_at = datetime.utcnow()
        session.commit()

        clips           = json.loads(clips_json)
        image_overlays  = json.loads(image_overlays_json)
        trim_args       = _build_trim_args(trim_start, trim_end)

        # ── Save image overlays to temp files ──────────────────────────────────────────
        img_temp_paths: list[str] = []
        for idx, ov in enumerate(image_overlays):
            p = _save_base64_image(ov["src"], export_id, idx)
            img_temp_paths.append(p)
            logger.info(f"[Export {export_id}] Image {idx}: {Path(p).name}")

        # Adjust subtitle timestamps when a trim-start offset is applied.
        # Every timestamp must shift left by trim_start seconds so subtitles
        # stay in sync with the newly trimmed video output.
        if trim_start > 0 or trim_end is not None:
            trim_dur = (trim_end - trim_start) if trim_end is not None else None
            adjusted: list[dict] = []
            for clip in clips:
                adj_s = float(clip["start"]) - trim_start
                adj_e = float(clip["end"])   - trim_start
                if adj_e <= 0:
                    continue
                if trim_dur is not None and adj_s >= trim_dur:
                    continue
                adjusted.append({
                    **clip,
                    "start": max(0.0, adj_s),
                    "end":   min(adj_e, trim_dur) if trim_dur else adj_e,
                })
            clips = adjusted
            logger.info(
                f"[Export {export_id}] Trim {trim_start:.2f}s–{trim_end}s; "
                f"{len(clips)} subtitle clips remain after adjustment."
            )

        # Resolve ffmpeg binary once
        ffmpeg_bin = str(_MMO_TOOL_ROOT / "ffmpeg.exe")
        if not Path(ffmpeg_bin).exists():
            ffmpeg_bin = "ffmpeg"

        # ── Per-segment voice synthesis ──────────────────────────────────────────
        if any(c.get("voice") for c in clips):
            logger.warning(
                "[Export %s] SubtitleClip.voice field detected in request but ignored: "
                "VoxCPM2 does not support per-segment named voice selection. "
                "Remove voice values from requests to suppress this warning.",
                export_id,
            )

        out = Path(OUTPUT_DIR) / f"export_{export_id}.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)

        # ── Build inputs list ──────────────────────────────────────────────
        # input 0  → source video
        # inputs 1…N → image files
        # optional extra input: composite audio (when per-segment voices used)
        cmd_base = [
            ffmpeg_bin, "-y",
            *trim_args["pre"],
            "-i", job.output_path,
        ]
        for p in img_temp_paths:
            cmd_base += ["-i", p]

        # ── Build filter_complex ──────────────────────────────────────────────
        video_w, video_h = _get_video_dimensions(job.output_path)
        filter_parts: list[str] = []
        video_label = "0:v"

        # Layer 1: image overlays
        if image_overlays and img_temp_paths:
            img_parts, video_label = _build_image_filter_chain(
                image_overlays, img_temp_paths, video_w, video_h
            )
            filter_parts.extend(img_parts)

        # Layer 2: subtitle burn (ASS for pixel-perfect match with canvas preview)
        if clips:
            srt_path = _create_ass_file(clips, export_id, video_w, video_h)
            logger.info(f"[Export {export_id}] ASS written: {srt_path}")
            escaped_sub = _escape_subtitle_path(srt_path)
            # No force_style needed — all styling is embedded in the ASS file
            sub_filter  = f"subtitles='{escaped_sub}'"

            if filter_parts:
                # Chain subtitle onto the last image-composited stream
                final_label = "vfinal"
                filter_parts.append(f"[{video_label}]{sub_filter}[{final_label}]")
                video_label = final_label
            else:
                # No image overlays — just a simple -vf
                pass  # handled below

        # ── Assemble final command ──────────────────────────────────────────────
        codec_args = [
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
        ]

        # Audio source: always use the original dubbed audio track
        audio_map = ["0:a:0"]

        if filter_parts:
            cmd = [
                *cmd_base,
                *trim_args["post"],
                "-filter_complex", ";".join(filter_parts),
                "-map", f"[{video_label}]",
                "-map", *audio_map,
                *codec_args,
                str(out),
            ]
        elif clips:
            # Simple subtitle-only (no images) — ASS file already created above
            assert srt_path is not None
            escaped_sub = _escape_subtitle_path(srt_path)
            cmd = [
                *cmd_base,
                *trim_args["post"],
                "-vf", f"subtitles='{escaped_sub}'",
                "-map", "0:v:0",
                "-map", *audio_map,
                *codec_args,
                str(out),
            ]
        else:
            # Trim-only (no subtitles, no images)
            cmd = [
                *cmd_base,
                *trim_args["post"],
                "-map", "0:v:0",
                "-map", *audio_map,
                *codec_args,
                str(out),
            ]

        logger.info(f"[Export {export_id}] Running FFmpeg…")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg subtitle burn failed:\n{proc.stderr[-800:]}")

        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("FFmpeg produced an empty output file.")

        export.status          = "DONE"
        export.output_path     = str(out)
        export.output_filename = out.name
        export.updated_at      = datetime.utcnow()
        session.commit()
        logger.info(f"[Export {export_id}] DONE → {out}")

    except Exception as exc:
        logger.error(f"[Export {export_id}] FAILED: {exc}", exc_info=True)
        try:
            if export:
                export.status        = "FAILED"
                export.error_message = str(exc)[:2000]
                export.updated_at    = datetime.utcnow()
                session.commit()
        except Exception as inner:
            logger.error(f"[Export {export_id}] could not persist FAILED status: {inner}")
    finally:
        # Clean up all temp files
        for tmp in ([srt_path] if srt_path else []) + img_temp_paths + seg_wav_paths + ([composite_audio_path] if composite_audio_path else []):
            try:
                Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass
        session.close()
