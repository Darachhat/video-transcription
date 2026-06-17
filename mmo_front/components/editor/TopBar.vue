<script setup lang="ts">
import { EDITOR_KEY } from '~/composables/useEditorState'

const editor = inject(EDITOR_KEY)!

// ── Timecode ────────────────────────────────────────────────────────────────
function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}
const timeDisplay = computed(
  () => `${fmtTime(editor.currentTime.value)} / ${fmtTime(editor.duration.value)}`
)

// ── Export state ─────────────────────────────────────────────────────────────
type ExportPhase = 'idle' | 'submitting' | 'processing' | 'done' | 'failed'

const config     = useRuntimeConfig()
const base       = config.public.apiBase as string

const phase      = ref<ExportPhase>('idle')
const exportErr  = ref('')
const exportId   = ref('')

let pollTimer: ReturnType<typeof setInterval> | null = null

function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onUnmounted(stopPoll)

async function handleExport() {
  // Only one export at a time
  if (phase.value === 'submitting' || phase.value === 'processing') return

  // Reset previous state
  phase.value     = 'submitting'
  exportErr.value = ''
  exportId.value  = ''
  stopPoll()

  try {
    // Build clip payload from current editor state
    const clips = editor.clips.value.map(c => ({
      id:    c.id,
      start: c.start,
      end:   c.end,
      text:  c.text,
      style: { ...c.style },
      voice: c.voice ?? null,
    }))

    const res = await fetch(`${base}/pipeline/jobs/${editor.jobId.value}/export`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        clips,
        image_overlays: editor.imageOverlays.value.map(img => ({
          name:    img.name,
          src:     img.src,
          x:       img.x,
          y:       img.y,
          width:   img.width,
          opacity: img.opacity,
        })),
        trim_start: editor.trimStart.value,
        trim_end:   editor.trimEnd.value,
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err?.response_msg || `Server error ${res.status}`)
    }

    const data = await res.json()
    exportId.value = data.data?.id ?? ''
    phase.value    = 'processing'

    // Poll for completion every 2 s
    pollTimer = setInterval(async () => {
      try {
        const poll = await fetch(`${base}/pipeline/exports/${exportId.value}`)
        if (!poll.ok) return
        const pollData = await poll.json()
        const status   = pollData.data?.status as string | undefined

        if (status === 'DONE') {
          stopPoll()
          phase.value = 'done'
          // Auto-trigger browser download
          const a     = document.createElement('a')
          a.href      = `${base}/pipeline/exports/${exportId.value}/download`
          a.download  = pollData.data?.output_filename ?? 'exported_dubbed.mp4'
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
        } else if (status === 'FAILED') {
          stopPoll()
          phase.value     = 'failed'
          exportErr.value = pollData.data?.error_message ?? 'Export failed.'
        }
      } catch { /* ignore transient poll errors */ }
    }, 2000)

  } catch (e: any) {
    stopPoll()
    phase.value     = 'failed'
    exportErr.value = e?.message ?? 'Failed to start export.'
  }
}

function resetExport() {
  stopPoll()
  phase.value     = 'idle'
  exportErr.value = ''
  exportId.value  = ''
}

const exportLabel = computed(() => {
  switch (phase.value) {
    case 'submitting':  return 'Submitting…'
    case 'processing':  return 'Exporting…'
    case 'done':        return 'Downloaded!'
    case 'failed':      return 'Retry Export'
    default:            return 'Export'
  }
})

const exportIcon = computed(() => {
  switch (phase.value) {
    case 'submitting':
    case 'processing': return 'progress_activity'
    case 'done':       return 'check_circle'
    case 'failed':     return 'error'
    default:           return 'download'
  }
})

const exportSpinning = computed(() =>
  phase.value === 'submitting' || phase.value === 'processing'
)

const exportBtnClass = computed(() => {
  if (phase.value === 'done')   return 'bg-emerald-600 hover:bg-emerald-700'
  if (phase.value === 'failed') return 'bg-red-600 hover:bg-red-700'
  return 'bg-[#7c3aed] hover:bg-[#6d28d9]'
})
</script>

<template>
  <!-- 44px top bar -->
  <header class="flex items-center gap-3 px-4 h-11 bg-[#1a1a1a] border-b border-[#2a2a2a] shrink-0 z-50">

    <!-- ── Left: back + project label ──────────────────────────────────── -->
    <NuxtLink
      to="/"
      title="Back to Dashboard"
      class="flex items-center justify-center w-7 h-7 rounded hover:bg-[#2a2a2a] text-gray-400 hover:text-white transition-colors"
    >
      <span class="material-symbols-outlined text-[18px]">arrow_back</span>
    </NuxtLink>

    <div class="w-px h-5 bg-[#2a2a2a]" />

    <span class="material-symbols-outlined text-[16px] text-gray-500">movie_edit</span>
    <span class="text-sm font-medium text-gray-200 max-w-[180px] truncate select-none">
      Dubbing Project
    </span>

    <!-- ── Center: timecode ──────────────────────────────────────────────── -->
    <div class="flex-1 flex justify-center">
      <div class="flex items-center gap-1.5 bg-[#111] border border-[#2a2a2a] rounded px-3 py-1">
        <span class="material-symbols-outlined text-[12px] text-gray-600">schedule</span>
        <span class="font-mono text-sm text-gray-200 tabular-nums tracking-wider">
          {{ timeDisplay }}
        </span>
      </div>
    </div>

    <!-- ── Right: subtitle count + settings + export ─────────────────────── -->
    <div class="flex items-center gap-2">

      <!-- Subtitle clip counter pill -->
      <div
        class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#2a2a2a] text-[10px] text-gray-400"
        :title="`${editor.clips.value.length} subtitle clips`"
      >
        <span class="material-symbols-outlined text-[12px]">subtitles</span>
        <span class="tabular-nums">{{ editor.clips.value.length }}</span>
      </div>

      <!-- Settings (placeholder) -->
      <button
        title="Settings"
        class="flex items-center justify-center w-7 h-7 rounded hover:bg-[#2a2a2a] text-gray-400 hover:text-white transition-colors"
      >
        <span class="material-symbols-outlined text-[18px]">settings</span>
      </button>

      <!-- Export button -->
      <div class="relative">
        <button
          :class="[
            'flex items-center gap-1.5 px-3 py-1.5 rounded text-white text-xs font-semibold transition-colors',
            exportBtnClass,
            (phase === 'submitting' || phase === 'processing') ? 'cursor-not-allowed opacity-80' : '',
          ]"
          :disabled="phase === 'submitting' || phase === 'processing'"
          @click="phase === 'done' ? resetExport() : handleExport()"
        >
          <span
            class="material-symbols-outlined text-[14px]"
            :class="exportSpinning ? 'animate-spin' : ''"
          >
            {{ exportIcon }}
          </span>
          {{ exportLabel }}
        </button>

        <!-- Error tooltip -->
        <div
          v-if="phase === 'failed' && exportErr"
          class="absolute right-0 top-full mt-1.5 w-64 bg-red-900/90 border border-red-500/50 rounded-lg p-2.5 z-50 text-[10px] text-red-200 leading-relaxed shadow-xl"
        >
          <div class="flex items-start gap-1.5">
            <span class="material-symbols-outlined text-[13px] text-red-400 shrink-0 mt-px">error</span>
            <span class="break-words">{{ exportErr }}</span>
          </div>
          <button
            class="mt-1.5 text-[9px] text-red-300 hover:text-white underline"
            @click="resetExport"
          >dismiss</button>
        </div>
      </div>
    </div>
  </header>
</template>
