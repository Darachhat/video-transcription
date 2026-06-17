<script setup lang="ts">
import { useEditorState, EDITOR_KEY } from '~/composables/useEditorState'
import { usePipeline } from '~/composables/usePipeline'

definePageMeta({
  layout: 'editor',
  pageTransition: false,   // editor is full-screen; no page slide animation needed
})

const route  = useRoute()
const jobId  = route.params.id as string
const { getJob, getDownloadUrl } = usePipeline()

// ── Initialise editor state ─────────────────────────────────────────────────
const editor = useEditorState()
provide(EDITOR_KEY, editor)

editor.jobId.value    = jobId
editor.videoUrl.value = getDownloadUrl(jobId)

// ── Load job data ───────────────────────────────────────────────────────────
const loading = ref(true)
const error   = ref('')

onMounted(async () => {
  try {
    const job = await getJob(jobId)
    if (!job) { error.value = 'Job not found.'; return }
    if (job.status !== 'DONE') { error.value = 'Job is not complete yet.'; return }

    // Load subtitle segments from the API
    // We stored segment metadata on the job; fetch full subtitle data from the pipeline result.
    // For now, we load the job's segment_count and reconstruct from the video duration.
    // The actual segments come via a dedicated API call (added below).
    await loadSubtitlesForJob(jobId)
  } catch (e: any) {
    error.value = e?.message || 'Failed to load editor.'
  } finally {
    loading.value = false
  }
})

async function loadSubtitlesForJob(id: string) {
  try {
    const config = useRuntimeConfig()
    const base   = config.public.apiBase as string
    const res    = await fetch(`${base}/pipeline/jobs/${id}/subtitles`)
    if (res.ok) {
      const data = await res.json()
      if (data.data && Array.isArray(data.data)) {
        editor.loadClips(data.data)
        return
      }
    }
  } catch { /* fallback: empty clips, user can add manually */ }
}

onUnmounted(() => editor.stopRender())
</script>

<template>
  <!--
    Single root element required: Vue's <Transition name="page"> cannot animate
    a fragment (multiple root nodes). Everything lives inside this one div so
    the page transition (even when disabled above) never hits the fragment case.
  -->
  <div class="flex flex-col h-full min-h-0">

    <!-- ── Loading ──────────────────────────────────────────── -->
    <div
      v-if="loading"
      class="flex-1 flex items-center justify-center gap-2 text-gray-400 text-sm"
    >
      <span class="material-symbols-outlined text-[20px] animate-spin">progress_activity</span>
      Loading editor…
    </div>

    <!-- ── Error ─────────────────────────────────────────────── -->
    <div
      v-else-if="error"
      class="flex-1 flex flex-col items-center justify-center gap-3 text-red-400"
    >
      <span class="material-symbols-outlined text-[40px]">error</span>
      <p class="text-sm">{{ error }}</p>
      <NuxtLink to="/" class="text-xs text-gray-400 hover:text-white underline">
        ← Back to Dashboard
      </NuxtLink>
    </div>

    <!-- ── Editor ────────────────────────────────────────────── -->
    <!-- <template v-else> unwraps into direct flex-col children of the outer div -->
    <template v-else>
      <EditorTopBar />

      <div class="flex flex-1 min-h-0">
        <EditorLeftPanel />
        <EditorPreviewPanel />
        <EditorRightPanel />
      </div>

      <EditorTimelinePanel />
    </template>

  </div>
</template>
