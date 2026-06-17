<script setup lang="ts">
import { EDITOR_KEY } from '~/composables/useEditorState'

const editor = inject(EDITOR_KEY)!

// ── Ruler tick generation ──────────────────────────────────────────────────
const RULER_HEIGHT = 28

const ticks = computed(() => {
  const dur   = editor.duration.value || 60
  const pps   = editor.pps.value
  // Pick a tick interval (1s, 2s, 5s, 10s, 30s) based on pps
  let interval = 1
  if (pps < 40)  interval = 5
  if (pps < 20)  interval = 10
  if (pps < 10)  interval = 30
  if (pps > 150) interval = 1
  const result: Array<{ time: number; label: string; x: number }> = []
  for (let t = 0; t <= dur; t += interval) {
    const m   = Math.floor(t / 60)
    const s   = t % 60
    const lbl = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
    result.push({ time: t, label: lbl, x: editor.timeToPx(t) })
  }
  return result
})

// ── Playhead drag ─────────────────────────────────────────────────────────
const timelineRef   = ref<HTMLDivElement | null>(null)
const isDraggingPH  = ref(false)

function startPlayheadDrag(e: MouseEvent) {
  isDraggingPH.value = true
  movePlayhead(e)
  window.addEventListener('mousemove', movePlayhead)
  window.addEventListener('mouseup',   stopPlayheadDrag, { once: true })
}

function movePlayhead(e: MouseEvent) {
  if (!timelineRef.value) return
  const rect = timelineRef.value.getBoundingClientRect()
  const x    = Math.max(0, e.clientX - rect.left + timelineRef.value.scrollLeft)
  editor.seek(editor.pxToTime(x))
}

function stopPlayheadDrag() {
  isDraggingPH.value = false
  window.removeEventListener('mousemove', movePlayhead)
}

function onRulerClick(e: MouseEvent) {
  if (!timelineRef.value) return
  const rect = timelineRef.value.getBoundingClientRect()
  const x    = e.clientX - rect.left + timelineRef.value.scrollLeft
  editor.seek(editor.pxToTime(x))
}

// ── Clip drag ────────────────────────────────────────────────────────────
function startClipDrag(e: MouseEvent, clipId: number) {
  e.stopPropagation()
  editor.selectClip(clipId)

  const clip       = editor.clips.value.find(c => c.id === clipId)
  if (!clip) return

  const dur        = clip.end - clip.start
  const startX     = e.clientX
  const origStart  = clip.start

  function onMove(ev: MouseEvent) {
    if (!timelineRef.value) return
    const dx      = ev.clientX - startX
    const dt      = editor.pxToTime(dx)
    const newStart = Math.max(0, Math.min(origStart + dt, (editor.duration.value || 60) - dur))
    editor.patchClip(clipId, { start: newStart, end: newStart + dur })
  }

  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup',   onUp)
  }

  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup',   onUp, { once: true })
}

// Resize clip (right handle)
function startClipResizeRight(e: MouseEvent, clipId: number) {
  e.stopPropagation()
  const clip    = editor.clips.value.find(c => c.id === clipId)
  if (!clip) return

  const startX  = e.clientX
  const origEnd = clip.end

  function onMove(ev: MouseEvent) {
    const dx     = ev.clientX - startX
    const dt     = editor.pxToTime(dx)
    const newEnd = Math.max(clip.start + 0.2, Math.min(origEnd + dt, editor.duration.value || 60))
    editor.patchClip(clipId, { end: newEnd })
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup',   onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup',   onUp, { once: true })
}

function startClipResizeLeft(e: MouseEvent, clipId: number) {
  e.stopPropagation()
  const clip      = editor.clips.value.find(c => c.id === clipId)
  if (!clip) return

  const startX    = e.clientX
  const origStart = clip.start

  function onMove(ev: MouseEvent) {
    const dx       = ev.clientX - startX
    const dt       = editor.pxToTime(dx)
    const newStart = Math.max(0, Math.min(origStart + dt, clip.end - 0.2))
    editor.patchClip(clipId, { start: newStart })
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup',   onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup',   onUp, { once: true })
}

// ── Trim handle drag ─────────────────────────────────────────────────────
function startTrimDrag(type: 'in' | 'out', e: MouseEvent) {
  e.stopPropagation()
  const origVal = type === 'in'
    ? editor.trimStart.value
    : (editor.trimEnd.value ?? editor.duration.value)
  const startX = e.clientX

  function onMove(ev: MouseEvent) {
    const dx     = ev.clientX - startX
    const dt     = editor.pxToTime(dx)
    const newVal = Math.max(0, Math.min(origVal + dt, editor.duration.value))
    if (type === 'in') {
      editor.trimStart.value = Math.min(
        newVal,
        (editor.trimEnd.value ?? editor.duration.value) - 0.1,
      )
    } else {
      editor.trimEnd.value = Math.max(newVal, editor.trimStart.value + 0.1)
    }
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp, { once: true })
}

// ── Zoom ─────────────────────────────────────────────────────────────────
function adjustZoom(delta: number) {
  editor.zoom.value = Math.max(0.25, Math.min(4, editor.zoom.value + delta))
}

// ── Timeline total width ──────────────────────────────────────────────────
const timelineWidth = computed(() => Math.max(editor.timeToPx(editor.duration.value || 60) + 200, 1000))

const playheadX = computed(() => editor.timeToPx(editor.currentTime.value))

// Track definitions
const TRACK_HEIGHT = 44
const TRACK_LABEL_WIDTH = 72

const TRACKS = [
  { id: 'video',    icon: 'smart_display', label: 'Video', color: '#3b82f6' },
  { id: 'subtitle', icon: 'subtitles',     label: 'Subs',  color: '#7c3aed' },
  { id: 'audio',    icon: 'graphic_eq',    label: 'Audio', color: '#10b981' },
] as const
</script>

<template>
  <!-- Timeline panel — fixed height at bottom -->
  <div class="h-[220px] flex flex-col bg-[#0f0f0f] border-t border-[#2a2a2a] shrink-0">

    <!-- ── Toolbar ────────────────────────────────────────────────────────── -->
    <div class="flex items-center gap-2 px-3 py-1.5 border-b border-[#2a2a2a] shrink-0 bg-[#111]">
      <!-- Track tools -->
      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" title="Add track">
        <span class="material-symbols-outlined text-[14px]">add</span>
      </button>
      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" title="Select">
        <span class="material-symbols-outlined text-[14px]">arrow_selector_tool</span>
      </button>
      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" title="Cut">
        <span class="material-symbols-outlined text-[14px]">content_cut</span>
      </button>

      <div class="w-px h-4 bg-[#2a2a2a] mx-1" />

      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" title="Snap">
        <span class="material-symbols-outlined text-[14px]">link</span>
      </button>
      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" title="Magnet">
        <span class="material-symbols-outlined text-[14px]">ads_click</span>
      </button>

      <div class="w-px h-4 bg-[#2a2a2a] mx-1" />

      <!-- Mark In -->
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-xs font-mono font-bold transition-all"
        :class="editor.trimStart.value > 0
          ? 'text-amber-400 bg-amber-500/15 border border-amber-500/30'
          : 'text-gray-500 hover:text-white hover:bg-[#2a2a2a]'"
        title="Mark In \u2014 set trim start to playhead"
        @click="editor.setTrimIn()"
      >I</button>

      <!-- Mark Out -->
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-xs font-mono font-bold transition-all"
        :class="editor.trimEnd.value !== null
          ? 'text-amber-400 bg-amber-500/15 border border-amber-500/30'
          : 'text-gray-500 hover:text-white hover:bg-[#2a2a2a]'"
        title="Mark Out \u2014 set trim end to playhead"
        @click="editor.setTrimOut()"
      >O</button>

      <!-- Clear trim (only visible when active) -->
      <button
        v-if="editor.isTrimActive.value"
        class="w-6 h-6 flex items-center justify-center rounded text-amber-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
        title="Clear trim"
        @click="editor.clearTrim()"
      >
        <span class="material-symbols-outlined text-[13px]">close</span>
      </button>

      <div class="flex-1" />

      <!-- Zoom controls -->
      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" @click="adjustZoom(-0.25)">
        <span class="material-symbols-outlined text-[14px]">zoom_out</span>
      </button>
      <div class="w-24 bg-[#1a1a1a] border border-[#2a2a2a] rounded-full h-1.5 relative cursor-pointer" @click="e => editor.zoom.value = Math.max(0.25, Math.min(4, editor.pxToTime((e.offsetX / 96) * 4 * 100)))">
        <div
          class="h-full bg-[#7c3aed] rounded-full"
          :style="{ width: ((editor.zoom.value - 0.25) / 3.75 * 100) + '%' }"
        />
        <div
          class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white shadow"
          :style="{ left: `calc(${(editor.zoom.value - 0.25) / 3.75 * 100}% - 6px)` }"
        />
      </div>
      <button class="w-6 h-6 flex items-center justify-center rounded text-gray-500 hover:text-white hover:bg-[#2a2a2a] transition-colors" @click="adjustZoom(0.25)">
        <span class="material-symbols-outlined text-[14px]">zoom_in</span>
      </button>
      <span class="text-[10px] text-gray-500 font-mono w-8 text-right">{{ editor.zoom.value.toFixed(1) }}x</span>
    </div>

    <!-- ── Track area ─────────────────────────────────────────────────────── -->
    <div class="flex flex-1 min-h-0 overflow-hidden">

      <!-- Track labels (fixed left column) -->
      <div class="shrink-0 flex flex-col border-r border-[#2a2a2a]" :style="{ width: TRACK_LABEL_WIDTH + 'px' }">
        <!-- Ruler spacer -->
        <div :style="{ height: RULER_HEIGHT + 'px' }" class="border-b border-[#2a2a2a] flex items-center justify-center">
          <span class="material-symbols-outlined text-[13px] text-gray-700">layers</span>
        </div>
        <!-- Track label rows -->
        <div
          v-for="track in TRACKS"
          :key="track.id"
          class="flex flex-col items-center justify-center gap-0.5 border-b border-[#1a1a1a]"
          :style="{ height: TRACK_HEIGHT + 'px' }"
          :title="track.label"
        >
          <span class="material-symbols-outlined text-[15px]" :style="{ color: track.color }">{{ track.icon }}</span>
          <span class="text-[8px] font-medium" :style="{ color: track.color + 'aa' }">{{ track.label }}</span>
        </div>
      </div>

      <!-- Scrollable timeline -->
      <div
        ref="timelineRef"
        class="flex-1 overflow-x-auto overflow-y-hidden relative"
        style="cursor: default;"
        @click.self="editor.selectClip(null)"
      >
        <div class="relative" :style="{ width: timelineWidth + 'px', minHeight: '100%' }">

          <!-- ── Ruler ─────────────────────────────────────────────────── -->
          <div
            class="sticky top-0 z-20 border-b border-[#2a2a2a] bg-[#0d0d0d] flex items-end"
            :style="{ height: RULER_HEIGHT + 'px' }"
            @mousedown="startPlayheadDrag"
            @click="onRulerClick"
            style="cursor: col-resize;"
          >
            <div
              v-for="tick in ticks"
              :key="tick.time"
              class="absolute bottom-0 flex flex-col items-start"
              :style="{ left: tick.x + 'px' }"
            >
              <span class="text-[9px] text-gray-500 ml-1 select-none">{{ tick.label }}</span>
              <div class="w-px h-1.5 bg-[#3a3a3a]" />
            </div>
          </div>

          <!-- ── Track rows ─────────────────────────────────────────────── -->

          <!-- Video track (full-width bar + trim overlays + handles) -->
          <div
            class="absolute border-b border-[#1a1a1a] flex items-center"
            :style="{
              top: RULER_HEIGHT + 'px',
              height: TRACK_HEIGHT + 'px',
              width: timelineWidth + 'px',
            }"
          >
            <!-- Base clip bar (dimmed when trim is active) -->
            <div
              v-if="editor.duration.value > 0"
              class="absolute rounded h-7 transition-opacity"
              :class="editor.isTrimActive.value ? 'opacity-20' : 'opacity-60'"
              :style="{
                left:  '0px',
                width: editor.timeToPx(editor.duration.value) + 'px',
                background: 'linear-gradient(90deg, #1d4ed8 0%, #3b82f6 100%)',
              }"
            >
              <span class="flex items-center gap-1 px-2 leading-7 select-none">
                <span class="material-symbols-outlined text-[12px] text-white/80">smart_display</span>
              </span>
            </div>

            <!-- Kept region highlight -->
            <div
              v-if="editor.isTrimActive.value && editor.duration.value > 0"
              class="absolute rounded h-7 opacity-70 pointer-events-none"
              :style="{
                left:  editor.timeToPx(editor.trimStart.value) + 'px',
                width: editor.timeToPx(editor.effectiveTrimEnd.value - editor.trimStart.value) + 'px',
                background: 'linear-gradient(90deg, #1d4ed8 0%, #3b82f6 100%)',
              }"
            />

            <!-- Trim In handle -->
            <div
              v-if="editor.isTrimActive.value"
              class="absolute top-0 h-full z-20 flex items-center cursor-ew-resize"
              :style="{ left: editor.timeToPx(editor.trimStart.value) + 'px' }"
              @mousedown.stop="startTrimDrag('in', $event)"
            >
              <div class="w-px h-full bg-amber-400" />
              <div class="w-2.5 h-5 rounded-r bg-amber-400 flex items-center justify-center gap-px -ml-px">
                <div class="w-px h-3 bg-amber-900/50" />
                <div class="w-px h-3 bg-amber-900/50" />
              </div>
            </div>

            <!-- Trim Out handle -->
            <div
              v-if="editor.trimEnd.value !== null"
              class="absolute top-0 h-full z-20 flex items-center cursor-ew-resize"
              :style="{ left: (editor.timeToPx(editor.trimEnd.value) - 10) + 'px' }"
              @mousedown.stop="startTrimDrag('out', $event)"
            >
              <div class="w-2.5 h-5 rounded-l bg-amber-400 flex items-center justify-center gap-px">
                <div class="w-px h-3 bg-amber-900/50" />
                <div class="w-px h-3 bg-amber-900/50" />
              </div>
              <div class="w-px h-full bg-amber-400" />
            </div>
          </div>

          <!-- Subtitle track (clips) -->
          <div
            class="absolute border-b border-[#1a1a1a]"
            :style="{
              top: (RULER_HEIGHT + TRACK_HEIGHT) + 'px',
              height: TRACK_HEIGHT + 'px',
              width: timelineWidth + 'px',
            }"
            @click.self="editor.selectClip(null)"
          >
            <!-- Empty state -->
            <div
              v-if="editor.clips.value.length === 0"
              class="absolute inset-0 flex items-center justify-center pointer-events-none"
            >
              <span class="text-[10px] text-gray-600">Drag material here and start to create</span>
            </div>

            <!-- Subtitle clips -->
            <div
              v-for="clip in editor.clips.value"
              :key="clip.id"
              class="absolute top-1.5 h-8 rounded cursor-grab active:cursor-grabbing flex items-center select-none overflow-hidden group border transition-all"
              :class="editor.selectedId.value === clip.id
                ? 'border-white/60 shadow-[0_0_0_1px_#7c3aed]'
                : 'border-transparent hover:border-white/20'"
              :style="{
                left:  editor.timeToPx(clip.start) + 'px',
                width: Math.max(editor.timeToPx(clip.end - clip.start), 20) + 'px',
                background: editor.selectedId.value === clip.id
                  ? 'linear-gradient(90deg, #6d28d9 0%, #7c3aed 100%)'
                  : 'linear-gradient(90deg, #4c1d95 0%, #5b21b6 100%)',
              }"
              @mousedown="startClipDrag($event, clip.id)"
              @click.stop="editor.selectClip(clip.id)"
            >
              <!-- Left resize handle -->
              <div
                class="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize opacity-0 group-hover:opacity-100 bg-white/20 rounded-l"
                @mousedown.stop="startClipResizeLeft($event, clip.id)"
              />
              <!-- Clip label -->
              <span class="text-[9px] text-white px-2 truncate pointer-events-none leading-tight">
                {{ clip.text.slice(0, 30) }}{{ clip.text.length > 30 ? '…' : '' }}
              </span>
              <!-- Right resize handle -->
              <div
                class="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize opacity-0 group-hover:opacity-100 bg-white/20 rounded-r"
                @mousedown.stop="startClipResizeRight($event, clip.id)"
              />
            </div>
          </div>

          <!-- Audio track (full-width bar, non-interactive) -->
          <div
            class="absolute border-b border-[#1a1a1a] flex items-center"
            :style="{
              top: (RULER_HEIGHT + TRACK_HEIGHT * 2) + 'px',
              height: TRACK_HEIGHT + 'px',
              width: timelineWidth + 'px',
            }"
          >
            <div
              v-if="editor.duration.value > 0"
              class="absolute rounded h-7 opacity-50"
              :style="{
                left: '0px',
                width: editor.timeToPx(editor.duration.value) + 'px',
                background: 'linear-gradient(90deg, #065f46 0%, #10b981 100%)',
              }"
            >
              <span class="flex items-center gap-1 px-2 leading-7 select-none">
                <span class="material-symbols-outlined text-[12px] text-white/80">graphic_eq</span>
              </span>
            </div>
          </div>

          <!-- ── Playhead ───────────────────────────────────────────────── -->
          <div
            class="absolute top-0 bottom-0 z-30 pointer-events-none"
            :style="{ left: playheadX + 'px', transform: 'translateX(-0.5px)' }"
          >
            <!-- Triangle head -->
            <div
              class="absolute top-0 left-1/2 -translate-x-1/2 w-0 h-0 pointer-events-auto cursor-col-resize"
              style="
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #7c3aed;
              "
              @mousedown="startPlayheadDrag"
            />
            <!-- Vertical line -->
            <div class="absolute top-2 bottom-0 left-1/2 -translate-x-1/2 w-px bg-[#7c3aed]" />
          </div>

        </div>
      </div>
    </div>
  </div>
</template>
