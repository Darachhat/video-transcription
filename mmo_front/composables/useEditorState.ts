/**
 * Core editor state — provided at page level, injected in every editor component.
 * One instance per editor page (not a singleton — recreated on each mount).
 */

export interface ImageOverlay {
  id: number;
  name: string;
  src: string; // base64 data URL
  x: number; // 0-100 % from left
  y: number; // 0-100 % from top
  width: number; // 1-100 % of container width
  opacity: number; // 0-1
}
export interface SubtitleStyle {
  fontFamily: string;
  fontSize: number;
  color: string;
  bgColor: string;
  bgOpacity: number;
  bold: boolean;
  italic: boolean;
  underline: boolean;
  align: "left" | "center" | "right";
  outlineColor: string;
  outlineWidth: number;
  positionY: number; // 0-100 % from top (85 = near bottom)
}

/**
 * VoxCPM2 quality presets.
 *
 * VoxCPM2 does not use named voices; synthesis quality is controlled by
 * cfg_value (classifier-free guidance scale) and inference_timesteps.
 * These presets expose those hyperparameters as user-facing options.
 *
 * NOTE: The SubtitleClip.voice field is retained as a no-op string for API
 * backward compatibility. It has no effect on VoxCPM2 synthesis output.
 */
export const VOXCPM_QUALITY_PRESETS = [
  { id: "balanced", label: "Balanced",     cfg_value: 2.0, inference_timesteps: 10 },
  { id: "quality",  label: "High Quality", cfg_value: 2.5, inference_timesteps: 15 },
  { id: "fast",     label: "Fast",         cfg_value: 1.5, inference_timesteps: 5  },
] as const;
export type VoxCPMPresetId = (typeof VOXCPM_QUALITY_PRESETS)[number]["id"];

export interface SubtitleClip {
  id: number;
  start: number; // seconds
  end: number; // seconds
  text: string;
  style: SubtitleStyle;
  /**
   * @deprecated VoxCPM2 does not support named voice selection.
   * Retained for API backward compatibility; ignored during synthesis.
   */
  voice: string | null;  // null = pipeline default (always used by VoxCPM2)
}

export const DEFAULT_STYLE: SubtitleStyle = {
  fontFamily: "Leelawadee UI",
  fontSize: 28,
  color: "#ffffff",
  bgColor: "#000000",
  bgOpacity: 0.65,
  bold: false,
  italic: false,
  underline: false,
  align: "center",
  outlineColor: "#000000",
  outlineWidth: 2,
  positionY: 88,
};

export function useEditorState() {
  // ── DOM refs (mounted by PreviewPanel) ─────────────────────────────────────
  const videoEl = ref<HTMLVideoElement | null>(null);
  const canvasEl = ref<HTMLCanvasElement | null>(null);

  // ── Video / job info ────────────────────────────────────────────────────────
  const jobId = ref("");
  const videoUrl = ref("");
  const duration = ref(0);

  // ── Video natural dimensions (set from loadedmetadata in PreviewPanel) ───────
  // Default to 16:9 until the real video is loaded.
  const videoWidth = ref(1280);
  const videoHeight = ref(720);
  /** Actual pixel ratio of the source video, e.g. 0.5625 for 9:16. */
  const videoAspectRatio = computed(() =>
    videoHeight.value > 0 ? videoWidth.value / videoHeight.value : 16 / 9,
  );
  /** True when the video is taller than it is wide (portrait / vertical). */
  const isPortrait = computed(() => videoHeight.value > videoWidth.value);

  // ── Playback ────────────────────────────────────────────────────────────────
  const currentTime = ref(0);
  const isPlaying = ref(false);
  const volume = ref(1);
  const muted = ref(false);

  // ── Timeline ────────────────────────────────────────────────────────────────
  const zoom = ref(1.0);
  const BASE_PPS = 100; // px/s at zoom 1×
  const pps = computed(() => BASE_PPS * zoom.value);

  // ── Clips ───────────────────────────────────────────────────────────────────
  const clips = ref<SubtitleClip[]>([]);
  const selectedId = ref<number | null>(null);
  const selected = computed(
    () => clips.value.find((c) => c.id === selectedId.value) ?? null,
  );

  // ── Panel tab ───────────────────────────────────────────────────────────────
  const activeTab = ref<"media" | "audio" | "text" | "sticker">("media");

  // ── Active default style ───────────────────────────────────────────────────
  // Starts as DEFAULT_STYLE; user can promote any clip's style to be the
  // new default with setAsDefault(). New clips and the "Apply to All" action
  // both use this reference.
  const activeDefaultStyle = ref<SubtitleStyle>({ ...DEFAULT_STYLE });

  // ── Image overlays ─────────────────────────────────────────────────────────
  const imageOverlays = ref<ImageOverlay[]>([]);
  const selectedImageId = ref<number | null>(null);
  const selectedImage = computed(
    () =>
      imageOverlays.value.find((i) => i.id === selectedImageId.value) ?? null,
  );

  // HTMLImageElement cache so canvas drawImage() never stalls waiting for decode
  const _imgCache = new Map<string, HTMLImageElement>();

  function _preloadImg(src: string): HTMLImageElement | null {
    let el = _imgCache.get(src);
    if (!el) {
      el = new Image();
      el.onload = () => _imgCache.set(src, el!);
      el.src = src;
      if (el.complete && el.naturalWidth > 0) _imgCache.set(src, el);
    }
    return el.naturalWidth > 0 ? el : null;
  }

  function addImageOverlay(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const src = e.target?.result as string;
      const maxId = Math.max(0, ...imageOverlays.value.map((i) => i.id));
      imageOverlays.value.push({
        id: maxId + 1,
        name: file.name,
        src,
        x: 5,
        y: 5,
        width: 20,
        opacity: 1.0,
      });
      selectedImageId.value = maxId + 1;
      selectedId.value = null; // deselect subtitle
      _preloadImg(src); // warm the cache
    };
    reader.readAsDataURL(file);
  }

  function updateImageOverlay(id: number, patch: Partial<ImageOverlay>) {
    const img = imageOverlays.value.find((i) => i.id === id);
    if (img) Object.assign(img, patch);
  }

  function deleteImageOverlay(id: number) {
    imageOverlays.value = imageOverlays.value.filter((i) => i.id !== id);
    if (selectedImageId.value === id) selectedImageId.value = null;
  }

  function selectImage(id: number | null) {
    selectedImageId.value = id;
    if (id !== null) selectedId.value = null; // deselect subtitle
  }

  // ── Trim region ─────────────────────────────────────────────────────────────
  // trimStart/trimEnd define the KEPT region. null trimEnd = keep to video end.
  const trimStart = ref(0);
  const trimEnd = ref<number | null>(null);

  const effectiveTrimEnd = computed(() => trimEnd.value ?? duration.value);
  const isTrimActive = computed(
    () =>
      trimStart.value > 0 ||
      (trimEnd.value !== null && trimEnd.value < duration.value),
  );

  function setTrimIn() {
    trimStart.value = Math.max(0, currentTime.value);
    if (trimEnd.value !== null && trimEnd.value <= trimStart.value)
      trimEnd.value = null;
  }
  function setTrimOut() {
    const t = currentTime.value;
    if (t > trimStart.value) trimEnd.value = t;
  }
  function clearTrim() {
    trimStart.value = 0;
    trimEnd.value = null;
  }

  // ── Playback actions ────────────────────────────────────────────────────────
  function play() {
    videoEl.value?.play();
    isPlaying.value = true;
  }
  function pause() {
    videoEl.value?.pause();
    isPlaying.value = false;
  }
  function togglePlay() {
    isPlaying.value ? pause() : play();
  }

  function seek(t: number) {
    const v = videoEl.value;
    if (!v) return;
    v.currentTime = Math.max(0, Math.min(t, duration.value));
    currentTime.value = v.currentTime;
  }

  function seekToStart() {
    seek(0);
  }
  function seekToEnd() {
    seek(duration.value);
  }

  // ── Clip management ─────────────────────────────────────────────────────────
  // Inline subtitle editing state
  const editingClipId = ref<number | null>(null);
  // Bounding boxes of last-rendered subtitle clips for hit-testing
  // key = clipId, value = { x, y, w, h } in canvas CSS pixels (not device pixels)
  const _subtitleBBoxes = new Map<
    number,
    { x: number; y: number; w: number; h: number }
  >();

  function startInlineEdit(id: number) {
    editingClipId.value = id;
    selectClip(id);
    pause(); // pause video while user types
  }
  function stopInlineEdit() {
    editingClipId.value = null;
    _renderFrame();
  }
  /** Hit-test canvas CSS coordinates against last rendered subtitle bboxes. */
  function hitTestSubtitle(cssX: number, cssY: number): number | null {
    for (const [id, box] of _subtitleBBoxes) {
      if (
        cssX >= box.x &&
        cssX <= box.x + box.w &&
        cssY >= box.y &&
        cssY <= box.y + box.h
      ) {
        return id;
      }
    }
    return null;
  }

  function loadClips(
    segs: Array<{ id: number; start: number; end: number; text: string }>,
  ) {
    clips.value = segs.map((s) => ({
      ...s,
      voice: null,
      style: { ...activeDefaultStyle.value },
    }));
  }

  function selectClip(id: number | null) {
    selectedId.value = id;
    if (id !== null) selectedImageId.value = null; // deselect image overlay
  }

  function patchClip(id: number, patch: Partial<Omit<SubtitleClip, "style">>) {
    const clip = clips.value.find((c) => c.id === id);
    if (clip) Object.assign(clip, patch);
  }

  function patchStyle(id: number, style: Partial<SubtitleStyle>) {
    const clip = clips.value.find((c) => c.id === id);
    if (clip) Object.assign(clip.style, style);
  }

  function deleteClip(id: number) {
    clips.value = clips.value.filter((c) => c.id !== id);
    if (selectedId.value === id) selectedId.value = null;
  }

  function addTextClip() {
    const maxId = Math.max(0, ...clips.value.map((c) => c.id));
    const start = currentTime.value;
    const newClip: SubtitleClip = {
      id: maxId + 1,
      start,
      end: Math.min(start + 3, duration.value || start + 3),
      text: "New Text",
      voice: null,
      style: { ...activeDefaultStyle.value },
    };
    clips.value.push(newClip);
    selectedId.value = newClip.id;
  }

  /**
   * Promote the selected clip's style to be the global default AND apply it
   * to every other clip in the timeline. The source clip is left unchanged.
   */
  function setAsDefault(clipId: number) {
    const source = clips.value.find((c) => c.id === clipId);
    if (!source) return;

    // Freeze a copy as the new default
    activeDefaultStyle.value = { ...source.style };

    // Push to every other clip
    for (const c of clips.value) {
      if (c.id !== clipId) {
        Object.assign(c.style, { ...source.style });
      }
    }

    _renderFrame();
  }

  // ── Timeline helpers ────────────────────────────────────────────────────────
  function timeToPx(t: number) {
    return t * pps.value;
  }
  function pxToTime(px: number) {
    return px / pps.value;
  }

  // ── Canvas subtitle rendering ────────────────────────────────────────────────

  /**
   * Break a single text segment into lines that fit within `maxWidth` pixels.
   * Splits on spaces; treats each existing word as the smallest unit.
   * Falls back to the whole segment if it cannot be broken (e.g. no spaces).
   */
  function _wrapLine(
    ctx: CanvasRenderingContext2D,
    text: string,
    maxWidth: number,
  ): string[] {
    if (!text) return [""];
    // If it already fits, return immediately
    if (ctx.measureText(text).width <= maxWidth) return [text];

    const words = text.split(" ");
    const result: string[] = [];
    let current = "";

    for (const word of words) {
      const candidate = current ? `${current} ${word}` : word;
      if (ctx.measureText(candidate).width > maxWidth && current !== "") {
        result.push(current);
        current = word;
      } else {
        current = candidate;
      }
    }
    if (current) result.push(current);
    return result.length ? result : [text];
  }

  let _raf: number | null = null;

  function startRender() {
    function frame() {
      if (videoEl.value && !videoEl.value.paused) {
        currentTime.value = videoEl.value.currentTime;
      }
      _renderFrame();
      _raf = requestAnimationFrame(frame);
    }
    _raf = requestAnimationFrame(frame);
  }

  function stopRender() {
    if (_raf !== null) {
      cancelAnimationFrame(_raf);
      _raf = null;
    }
  }

  function _renderFrame() {
    const canvas = canvasEl.value;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Keep canvas pixel size in sync with its CSS display size
    const W = canvas.offsetWidth || 640;
    const H = canvas.offsetHeight || 360;
    if (canvas.width !== W || canvas.height !== H) {
      canvas.width = W;
      canvas.height = H;
    }

    ctx.clearRect(0, 0, W, H);

    const t = currentTime.value;
    // Image overlays (below subtitles)
    for (const img of imageOverlays.value) {
      const el = _preloadImg(img.src);
      if (!el) continue;
      const ix = (img.x / 100) * W;
      const iy = (img.y / 100) * H;
      const iw = (img.width / 100) * W;
      const ih =
        el.naturalWidth > 0 ? iw * (el.naturalHeight / el.naturalWidth) : iw;
      ctx.globalAlpha = img.opacity;
      ctx.drawImage(el, ix, iy, iw, ih);
      ctx.globalAlpha = 1;
    }
    // Subtitle clips (above images) — skip the one being inline-edited
    _subtitleBBoxes.clear();
    for (const clip of clips.value) {
      if (t >= clip.start && t <= clip.end) {
        if (clip.id === editingClipId.value) {
          // Store approximate bbox so the inline editor can position itself,
          // but don't draw — the floating <textarea> replaces it.
          const s = clip.style;
          const fs = Math.max(10, Math.round(s.fontSize * (H / 480)));
          const lh = fs * 1.4;
          const boxH = lh * 2; // rough estimate
          const boxY = (s.positionY / 100) * H - boxH;
          _subtitleBBoxes.set(clip.id, {
            x: W * 0.06,
            y: boxY,
            w: W * 0.88,
            h: boxH + lh,
          });
          continue;
        }
        _renderClip(ctx, clip, W, H);
      }
    }
  }

  function _renderClip(
    ctx: CanvasRenderingContext2D,
    clip: SubtitleClip,
    W: number,
    H: number,
  ) {
    const s = clip.style;
    const scale = H / 480;
    const fs = Math.max(10, Math.round(s.fontSize * scale));

    ctx.save();

    const fontStr = [
      s.italic ? "italic" : "",
      s.bold ? "bold" : "",
      `${fs}px`,
      `"${s.fontFamily}", "Leelawadee UI", sans-serif`,
    ]
      .filter(Boolean)
      .join(" ");

    ctx.font = fontStr;
    ctx.textAlign = s.align as CanvasTextAlign;
    ctx.textBaseline = "alphabetic";

    // Maximum subtitle width = 88% of canvas, leaving 6% margin each side.
    // Two-pass: first split on explicit newlines, then word-wrap each segment.
    const maxSubW = W * 0.88;
    const lines: string[] = clip.text
      .split("\n")
      .flatMap((seg) => _wrapLine(ctx, seg.trim(), maxSubW));
    const lh = fs * 1.4;
    const totalH = lh * lines.length;
    const baseY = (s.positionY / 100) * H;
    const startY = baseY - totalH + lh;
    const xPos = s.align === "left" ? 20 : s.align === "right" ? W - 20 : W / 2;

    // Background
    if (s.bgOpacity > 0) {
      ctx.globalAlpha = s.bgOpacity;
      ctx.fillStyle = s.bgColor;
      lines.forEach((line, i) => {
        const m = ctx.measureText(line);
        const bx =
          s.align === "center"
            ? xPos - m.width / 2 - 6
            : s.align === "right"
              ? xPos - m.width - 6
              : xPos - 6;
        ctx.fillRect(bx, startY + i * lh - fs - 3, m.width + 12, fs + 10);
      });
      ctx.globalAlpha = 1;
    }

    // Outline
    if (s.outlineWidth > 0) {
      ctx.strokeStyle = s.outlineColor;
      ctx.lineWidth = s.outlineWidth;
      lines.forEach((line, i) => ctx.strokeText(line, xPos, startY + i * lh));
    }

    // Text fill
    ctx.fillStyle = s.color;
    lines.forEach((line, i) => ctx.fillText(line, xPos, startY + i * lh));

    // Underline
    if (s.underline) {
      lines.forEach((line, i) => {
        const m = ctx.measureText(line);
        const lx =
          s.align === "center"
            ? xPos - m.width / 2
            : s.align === "right"
              ? xPos - m.width
              : xPos;
        ctx.fillStyle = s.color;
        ctx.fillRect(lx, startY + i * lh + 4, m.width, 2);
      });
    }

    ctx.restore();
    // Record bbox in CSS pixels for hit-testing.
    // ctx.canvas is always the canvas element; we convert device-px → CSS-px.
    const bboxScale =
      ctx.canvas.offsetWidth / (ctx.canvas.width || ctx.canvas.offsetWidth);
    const bboxStyle = clip.style;
    const bboxFs = Math.max(10, Math.round(bboxStyle.fontSize * (H / 480)));
    const bboxLh = bboxFs * 1.4;
    const bboxLineN = clip.text.split("\n").length;
    const bboxH = bboxLh * bboxLineN;
    const bboxY = ((bboxStyle.positionY / 100) * H - bboxH) * bboxScale;
    const bboxX = W * 0.06 * bboxScale;
    _subtitleBBoxes.set(clip.id, {
      x: bboxX,
      y: bboxY,
      w: W * 0.88 * bboxScale,
      h: (bboxH + bboxLh) * bboxScale,
    });
  }

  return {
    // DOM refs
    videoEl,
    canvasEl,
    // Info
    jobId,
    videoUrl,
    duration,
    videoWidth,
    videoHeight,
    videoAspectRatio,
    isPortrait,
    // Playback
    currentTime,
    isPlaying,
    volume,
    muted,
    // Timeline
    zoom,
    pps,
    // Clips
    clips,
    selectedId,
    selected,
    // UI
    activeTab,
    // Inline subtitle editing
    editingClipId,
    startInlineEdit,
    stopInlineEdit,
    hitTestSubtitle,
    // Image overlays
    imageOverlays,
    selectedImageId,
    selectedImage,
    addImageOverlay,
    updateImageOverlay,
    deleteImageOverlay,
    selectImage,
    // Trim
    trimStart,
    trimEnd,
    effectiveTrimEnd,
    isTrimActive,
    setTrimIn,
    setTrimOut,
    clearTrim,
    // Actions
    play,
    pause,
    togglePlay,
    seek,
    seekToStart,
    seekToEnd,
    loadClips,
    selectClip,
    patchClip,
    patchStyle,
    deleteClip,
    addTextClip,
    timeToPx,
    pxToTime,
    startRender,
    stopRender,
    _renderFrame,
    setAsDefault,
  };
}

export type EditorState = ReturnType<typeof useEditorState>;
export const EDITOR_KEY = Symbol("editor") as InjectionKey<EditorState>;
