<script setup lang="ts">
import { EDITOR_KEY } from '~/composables/useEditorState'

const editor = inject(EDITOR_KEY)!

const wrapperRef      = ref<HTMLDivElement | null>(null)
const videoContainerRef = ref<HTMLDivElement | null>(null)

// ── Image overlay drag & resize ─────────────────────────────────────────────
function startImageDrag(imgId: number, e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()

  const img = editor.imageOverlays.value.find(i => i.id === imgId)
  if (!img) return
  editor.selectImage(imgId)

  const container = videoContainerRef.value
  if (!container) return

  // Snapshot the starting state at mousedown time
  const startX = e.clientX
  const startY = e.clientY
  const origX  = img.x
  const origY  = img.y
  const origW  = img.width

  function onMove(ev: MouseEvent) {
    // Re-read the container rect on every move to handle scroll/resize
    const r  = container.getBoundingClientRect()
    const dx = ((ev.clientX - startX) / r.width)  * 100
    const dy = ((ev.clientY - startY) / r.height) * 100
    editor.updateImageOverlay(imgId, {
      x: Math.max(0, Math.min(origX + dx, 100 - origW)),
      y: Math.max(0, Math.min(origY + dy, 95)),
    })
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup',   onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup',   onUp, { once: true })
}

function startImageResize(imgId: number, e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()

  const img = editor.imageOverlays.value.find(i => i.id === imgId)
  if (!img) return

  const container = videoContainerRef.value
  if (!container) return

  const startX = e.clientX
  const origW  = img.width
  const origX  = img.x

  function onMove(ev: MouseEvent) {
    const r  = container.getBoundingClientRect()
    const dw = ((ev.clientX - startX) / r.width) * 100
    editor.updateImageOverlay(imgId, {
      width: Math.max(5, Math.min(origW + dw, 100 - origX)),
    })
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup',   onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup',   onUp, { once: true })
}

// ── Wire up video & canvas elements when mounted ────────────────────────────
onMounted(() => {
  const video  = wrapperRef.value?.querySelector('video')  as HTMLVideoElement | null
  const canvas = wrapperRef.value?.querySelector('canvas') as HTMLCanvasElement | null
  if (video)  editor.videoEl.value  = video
  if (canvas) editor.canvasEl.value = canvas

  if (video) {
    video.addEventListener('loadedmetadata', () => {
      editor.duration.value    = video.duration
      // Capture the real video dimensions so the preview and canvas
      // resize to match the actual aspect ratio (portrait, landscape, square)
      editor.videoWidth.value  = video.videoWidth  || 1280
      editor.videoHeight.value = video.videoHeight || 720
    })
    video.addEventListener('timeupdate',     () => { editor.currentTime.value = video.currentTime })
    video.addEventListener('play',           () => { editor.isPlaying.value = true })
    video.addEventListener('pause',          () => { editor.isPlaying.value = false })
    video.addEventListener('ended',          () => { editor.isPlaying.value = false })
    video.volume = editor.volume.value
  }

  editor.startRender()
})

onUnmounted(() => editor.stopRender())

// Volume sync
watch(() => editor.volume.value, v => {
  if (editor.videoEl.value) editor.videoEl.value.volume = v
})
watch(() => editor.muted.value, m => {
  if (editor.videoEl.value) editor.videoEl.value.muted = m
})

// ── Progress bar interaction ────────────────────────────────────────────────
const progressRef = ref<HTMLDivElement | null>(null)

function onProgressClick(e: MouseEvent) {
  if (!progressRef.value) return
  const rect  = progressRef.value.getBoundingClientRect()
  const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  editor.seek(ratio * editor.duration.value)
}

const progressPercent = computed(() =>
  editor.duration.value > 0
    ? (editor.currentTime.value / editor.duration.value) * 100
    : 0
)

function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2,'0')}:${String(Math.floor(s % 60)).padStart(2,'0')}`
}

// ── Subtitle inline editing ──────────────────────────────────────────────
const inlineRef = ref<HTMLTextAreaElement | null>(null)

// The clip currently being edited (if any)
const editingClip = computed(() =>
  editor.clips.value.find(c => c.id === editor.editingClipId.value) ?? null
)

// Auto-focus the textarea whenever we enter edit mode
watch(() => editor.editingClipId.value, async (id) => {
  if (id !== null) {
    await nextTick()
    inlineRef.value?.focus()
    inlineRef.value?.select()
  }
})

// Background click on the video container:
// Canvas has pointer-events:none, so clicks on the canvas area fall through here.
// Image divs use @click.stop so they never bubble here.
// This handler: hit-test subtitles → inline edit, else deselect + play/pause.
function onContainerClick(e: MouseEvent) {
  const canvas = editor.canvasEl.value
  if (!canvas) { editor.togglePlay(); return }
  const rect = canvas.getBoundingClientRect()
  const cx   = e.clientX - rect.left
  const cy   = e.clientY - rect.top
  const hit  = editor.hitTestSubtitle(cx, cy)
  if (hit !== null) {
    editor.startInlineEdit(hit)
  } else {
    editor.stopInlineEdit()
    editor.selectImage(null)
    editor.selectClip(null)
    editor.togglePlay()
  }
}
</script>

<template>
  <!-- Flex center column: preview takes remaining space -->
  <div class="flex-1 flex flex-col bg-[#0f0f0f] min-w-0">

    <!-- Video area — fills available height, centered -->
    <div ref="wrapperRef" class="flex-1 flex items-center justify-center relative overflow-hidden min-h-0 bg-[#070707]">
      <!--
        Container matches the video's real aspect ratio.
        max-width + max-height let the browser fit it within the available space
        without overflow, regardless of whether the video is portrait or landscape.
      -->
      <!--
        Layer order (bottom → top):
          z=0   video element          →  @click.stop → togglePlay (only when no overlay above)
          z=10  canvas                 →  pointer-events:none  (renders images + subtitles visually)
          z=12  image overlay divs     →  pointer-events:auto  (drag / resize / select)
          z=14  inline subtitle editor →  pointer-events:auto  (typing)
          z=15  play overlay icon      →  pointer-events:none  (cosmetic)
        The container @click fires only when clicks fall through all children
        (canvas is none; image divs stop propagation; video stops propagation).
      -->
      <div
        ref="videoContainerRef"
        class="relative bg-black flex-shrink-0"
        :style="{
          aspectRatio: `${editor.videoWidth.value} / ${editor.videoHeight.value}`,
          maxWidth:  '100%',
          maxHeight: '100%',
          cursor:    editor.editingClipId.value ? 'text' : 'default',
        }"
        @click="onContainerClick"
      >
        <!-- z=0: Video (click → togglePlay, stops propagation so container click is not triggered) -->
        <video
          class="w-full h-full object-contain"
          :src="editor.videoUrl.value"
          preload="metadata"
          @click.stop="editor.togglePlay()"
        />

        <!-- z=10: Canvas — VISUAL ONLY, pointer-events:none so all mouse events pass through -->
        <canvas
          class="absolute inset-0 w-full h-full pointer-events-none"
          style="z-index: 10;"
        />

        <!-- z=12: Image overlay divs — ABOVE canvas, fully interactive -->
        <div
          v-for="img in editor.imageOverlays.value"
          :key="img.id"
          class="absolute select-none group/img"
          :style="{
            left:          img.x + '%',
            top:           img.y + '%',
            width:         img.width + '%',
            opacity:       img.opacity,
            zIndex:        12,
            cursor:        'move',
          }"
          @mousedown.stop="startImageDrag(img.id, $event)"
          @click.stop="editor.selectImage(img.id)"
        >
          <!-- Actual image -->
          <img
            :src="img.src"
            class="w-full h-auto block pointer-events-none select-none"
            draggable="false"
          />

          <!-- Selection ring (violet outline when selected) -->
          <div
            v-if="editor.selectedImageId.value === img.id"
            class="absolute inset-0 rounded-sm pointer-events-none"
            style="box-shadow: 0 0 0 2px #7c3aed, 0 0 0 4px rgba(124,58,237,0.3);"
          />

          <!-- Corner resize handle (bottom-right) — only when selected -->
          <div
            v-if="editor.selectedImageId.value === img.id"
            class="absolute -bottom-1.5 -right-1.5 w-4 h-4 bg-[#7c3aed] rounded-full
                   border-2 border-white shadow-lg cursor-se-resize"
            @mousedown.stop="startImageResize(img.id, $event)"
          />

          <!-- Drag indicator badge (top-left, only when selected) -->
          <div
            v-if="editor.selectedImageId.value === img.id"
            class="absolute -top-5 left-0 flex items-center gap-1 bg-[#7c3aed] text-white
                   text-[9px] px-1.5 py-0.5 rounded pointer-events-none select-none"
          >
            <span class="material-symbols-outlined text-[10px]">open_with</span>
            {{ img.name.slice(0, 16) }}
          </div>
        </div>

        <!-- z=14: Inline subtitle editor — appears over the subtitle position -->
        <div
          v-if="editingClip"
          class="absolute inset-x-[6%] flex flex-col items-center"
          :style="{
            top:       editingClip.style.positionY + '%',
            transform: 'translateY(-100%)',
            zIndex:    14,
          }"
          @click.stop
        >
          <textarea
            ref="inlineRef"
            :value="editingClip.text"
            rows="2"
            class="w-full resize-none rounded outline-none text-center
                   bg-black/75 backdrop-blur-sm px-2 py-1"
            :style="{
              fontFamily:   editingClip.style.fontFamily + ', Leelawadee UI, sans-serif',
              fontSize:     Math.max(10, editingClip.style.fontSize * 0.55) + 'px',
              color:        editingClip.style.color,
              lineHeight:   '1.4',
              border:       '2px solid #7c3aed',
              borderRadius: '4px',
              caretColor:   '#7c3aed',
            }"
            @input="editor.patchClip(editingClip.id, { text: ($event.target as HTMLTextAreaElement).value }); editor._renderFrame()"
            @blur="editor.stopInlineEdit()"
            @keydown.escape.prevent="editor.stopInlineEdit()"
            @keydown.enter.ctrl="editor.stopInlineEdit()"
          />
          <p class="text-[9px] text-gray-400 mt-0.5 select-none">
            <span class="material-symbols-outlined text-[10px] align-middle">keyboard_return</span>
            Ctrl+Enter or Esc to finish
          </p>
        </div>

        <!-- z=15: Play-pause icon overlay — cosmetic only -->
        <Transition name="fade-fast">
          <div
            v-if="!editor.isPlaying.value"
            class="absolute inset-0 flex items-center justify-center pointer-events-none"
            style="z-index: 15;"
          >
            <div class="w-14 h-14 rounded-full bg-black/50 flex items-center justify-center">
              <span class="material-symbols-outlined text-white text-[30px]">play_arrow</span>
            </div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- ── Controls bar ──────────────────────────────────────────────────── -->
    <div class="shrink-0 flex flex-col gap-2 px-4 py-3 bg-[#111] border-t border-[#2a2a2a]">
      <!-- Progress bar -->
      <div
        ref="progressRef"
        class="h-1.5 bg-[#2a2a2a] rounded-full cursor-pointer group relative"
        @click="onProgressClick"
      >
        <!-- Trim kept-region tint (amber) -->
        <div
          v-if="editor.isTrimActive.value && editor.duration.value > 0"
          class="absolute top-0 h-full bg-amber-400/25 rounded pointer-events-none border-x border-amber-400/50"
          :style="{
            left:  (editor.trimStart.value / editor.duration.value * 100) + '%',
            width: ((editor.effectiveTrimEnd.value - editor.trimStart.value) / editor.duration.value * 100) + '%',
          }"
        />
        <!-- Playback fill -->
        <div
          class="h-full bg-[#7c3aed] rounded-full transition-none relative z-10"
          :style="{ width: progressPercent + '%' }"
        />
        <!-- Trim In marker line -->
        <div
          v-if="editor.isTrimActive.value && editor.duration.value > 0"
          class="absolute top-1/2 -translate-y-1/2 w-0.5 h-3.5 bg-amber-400 rounded-full pointer-events-none z-20"
          :style="{ left: (editor.trimStart.value / editor.duration.value * 100) + '%' }"
        />
        <!-- Trim Out marker line -->
        <div
          v-if="editor.trimEnd.value !== null && editor.duration.value > 0"
          class="absolute top-1/2 -translate-y-1/2 w-0.5 h-3.5 bg-amber-400 rounded-full pointer-events-none z-20"
          :style="{ left: (editor.trimEnd.value / editor.duration.value * 100) + '%' }"
        />
        <!-- Playhead thumb -->
        <div
          class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow opacity-0 group-hover:opacity-100 transition-opacity z-30"
          :style="{ left: `calc(${progressPercent}% - 6px)` }"
        />
      </div>

      <!-- Transport controls row -->
      <div class="flex items-center gap-1">
        <!-- To start -->
        <button
          class="w-7 h-7 rounded flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#2a2a2a] transition-colors"
          @click="editor.seekToStart()"
        >
          <span class="material-symbols-outlined text-[18px]">skip_previous</span>
        </button>

        <!-- Play/Pause -->
        <button
          class="w-8 h-8 rounded flex items-center justify-center bg-white/10 hover:bg-white/20 text-white transition-colors"
          @click="editor.togglePlay()"
        >
          <span class="material-symbols-outlined text-[20px]">
            {{ editor.isPlaying.value ? 'pause' : 'play_arrow' }}
          </span>
        </button>

        <!-- To end -->
        <button
          class="w-7 h-7 rounded flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#2a2a2a] transition-colors"
          @click="editor.seekToEnd()"
        >
          <span class="material-symbols-outlined text-[18px]">skip_next</span>
        </button>

        <!-- Timecode -->
        <span class="ml-2 font-mono text-xs text-gray-300 tabular-nums">
          {{ fmtTime(editor.currentTime.value) }} / {{ fmtTime(editor.duration.value) }}
        </span>

        <!-- Spacer -->
        <div class="flex-1" />

        <!-- Mute -->
        <button
          class="w-7 h-7 rounded flex items-center justify-center text-gray-400 hover:text-white hover:bg-[#2a2a2a] transition-colors"
          @click="editor.muted.value = !editor.muted.value"
        >
          <span class="material-symbols-outlined text-[18px]">
            {{ editor.muted.value ? 'volume_off' : 'volume_up' }}
          </span>
        </button>

        <!-- Volume slider -->
        <input
          type="range" min="0" max="1" step="0.02"
          :value="editor.volume.value"
          class="w-20 accent-[#7c3aed]"
          @input="editor.volume.value = Number(($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>

  </div>
</template>

<style scoped>
.fade-fast-enter-active, .fade-fast-leave-active { transition: opacity 0.15s ease; }
.fade-fast-enter-from, .fade-fast-leave-to       { opacity: 0; }
</style>
