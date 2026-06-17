<script setup lang="ts">
import type { Job } from '~/composables/usePipeline'
import { usePipeline, STAGE_LABELS } from '~/composables/usePipeline'

const route = useRoute()
const jobId = route.params.id as string

const { getJob, waitForJobUpdate, getDownloadUrl, formatBytes, formatDate, timeElapsed, deleteJob } = usePipeline()

const job = ref<Job | null>(null)
const loading = ref(true)
const error = ref('')

async function fetchJob() {
  try {
    job.value = await getJob(jobId)
    if (!job.value) error.value = 'Job not found.'
  } catch (e: any) {
    error.value = e?.message || 'Failed to load job.'
  } finally {
    loading.value = false
  }
}

let pollActive = false

onMounted(async () => {
  await fetchJob()

  // Long-poll loop: one open request at a time, returns as soon as status changes
  pollActive = true
  while (pollActive && job.value && !['DONE', 'FAILED'].includes(job.value.status)) {
    try {
      const updated = await waitForJobUpdate(jobId, job.value.status)
      if (!pollActive) break
      if (updated) job.value = updated
    } catch {
      // Network hiccup — wait a moment then retry
      await new Promise(r => setTimeout(r, 2000))
    }
  }
})

onUnmounted(() => { pollActive = false })

const currentStageLabel = computed(() =>
  job.value ? (STAGE_LABELS[job.value.status] ?? job.value.status) : ''
)

const isTerminal = computed(() =>
  job.value ? ['DONE', 'FAILED'].includes(job.value.status) : false
)

const downloadUrl = computed(() => getDownloadUrl(jobId))

async function handleDelete() {
  if (!confirm('Delete this job?')) return
  try {
    await deleteJob(jobId)
    await navigateTo('/')
  } catch {}
}
</script>

<template>
  <div class="min-h-screen p-6 max-w-4xl mx-auto">
    <!-- Back -->
    <NuxtLink to="/" class="inline-flex items-center gap-1.5 text-sm text-gray-400 hover:text-white mb-6 transition-colors">
      <span class="material-symbols-outlined text-[16px]">arrow_back</span>
      Back to Dashboard
    </NuxtLink>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-4 animate-pulse">
      <div class="h-8 bg-surface rounded-lg w-1/2" />
      <div class="h-4 bg-surface rounded w-3/4" />
      <div class="h-48 bg-surface rounded-xl mt-6" />
    </div>

    <!-- Error -->
    <div v-else-if="error || !job" class="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-red-400">
      <span class="material-symbols-outlined text-3xl block mb-2">error</span>
      {{ error || 'Job not found.' }}
    </div>

    <!-- Job detail -->
    <div v-else class="space-y-5">
      <!-- Title row -->
      <div class="flex items-start justify-between gap-4">
        <div class="min-w-0">
          <div class="flex items-center gap-3 mb-1">
            <UiStatusBadge :status="job.status" />
            <span class="text-gray-500 text-sm">{{ formatDate(job.created_at) }}</span>
          </div>
          <p class="text-gray-300 text-sm font-mono break-all">{{ job.url }}</p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <NuxtLink
            v-if="job.status === 'DONE'"
            :to="`/editor/${job.id}`"
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#1a1a2e] border border-[#7c3aed]/40 hover:bg-[#7c3aed]/20 text-[#a78bfa] text-sm font-medium transition-colors"
          >
            <span class="material-symbols-outlined text-[16px]">movie_edit</span>
            Open Editor
          </NuxtLink>
          <a
            v-if="job.status === 'DONE'"
            :href="downloadUrl"
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors"
            download
          >
            <span class="material-symbols-outlined text-[16px]">download</span>
            Download MP4
          </a>
          <button
            class="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
            title="Delete job"
            @click="handleDelete"
          >
            <span class="material-symbols-outlined text-[18px]">delete</span>
          </button>
        </div>
      </div>

      <!-- Main grid -->
      <div class="grid md:grid-cols-[1fr_280px] gap-5">
        <!-- Left: Progress + Video -->
        <div class="space-y-5">
          <!-- Current status banner -->
          <div
            v-if="!isTerminal"
            class="flex items-center gap-3 bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-3"
          >
            <span class="material-symbols-outlined text-blue-400 animate-spin-slow text-[20px]">progress_activity</span>
            <div>
              <p class="text-sm font-medium text-blue-300">{{ currentStageLabel }}</p>
              <p class="text-xs text-blue-400/60">Pipeline is running… auto-refreshing</p>
            </div>
          </div>

          <div
            v-else-if="job.status === 'DONE'"
            class="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-3"
          >
            <span class="material-symbols-outlined text-emerald-400 text-[20px]">check_circle</span>
            <div>
              <p class="text-sm font-medium text-emerald-300">Dubbing Complete</p>
              <p class="text-xs text-emerald-400/60">
                {{ formatBytes(job.output_size_bytes) }} ·
                {{ timeElapsed(job.created_at, job.updated_at) }} elapsed
              </p>
            </div>
          </div>

          <div
            v-else
            class="flex items-center gap-3 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3"
          >
            <span class="material-symbols-outlined text-red-400 text-[20px]">cancel</span>
            <div>
              <p class="text-sm font-medium text-red-300">Pipeline Failed</p>
              <p class="text-xs text-red-400/70 font-mono break-all">{{ job.error_message }}</p>
            </div>
          </div>

          <!-- Video player -->
          <div
            v-if="job.status === 'DONE'"
            class="bg-surface border border-border rounded-xl overflow-hidden"
          >
            <div class="px-4 py-3 border-b border-border flex items-center gap-2">
              <span class="material-symbols-outlined text-gray-400 text-[16px]">play_circle</span>
              <span class="text-sm text-gray-300 font-medium">Dubbed Output</span>
              <span class="ml-auto text-xs text-gray-500 font-mono">{{ job.output_filename }}</span>
            </div>
            <video
              controls
              class="w-full max-h-[400px] bg-black"
              preload="metadata"
            >
              <source :src="downloadUrl" type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>
        </div>

        <!-- Right: Stage timeline + metadata -->
        <div class="space-y-4">
          <!-- Pipeline stages -->
          <div class="bg-surface border border-border rounded-xl p-4">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Pipeline Stages</p>
            <ProgressTimeline :status="job.status" :error-message="job.error_message" />
          </div>

          <!-- Metadata -->
          <div class="bg-surface border border-border rounded-xl p-4">
            <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Metadata</p>
            <dl class="space-y-2">
              <div class="flex justify-between text-xs">
                <dt class="text-gray-500">Whisper model</dt>
                <dd class="text-gray-200 font-mono">{{ job.whisper_model }}</dd>
              </div>
              <div v-if="job.detected_language" class="flex justify-between text-xs">
                <dt class="text-gray-500">Source language</dt>
                <dd class="text-gray-200 font-mono">{{ job.detected_language }}</dd>
              </div>
              <div v-if="job.transcript_length" class="flex justify-between text-xs">
                <dt class="text-gray-500">Transcript length</dt>
                <dd class="text-gray-200 font-mono">{{ job.transcript_length }} chars</dd>
              </div>
              <div v-if="job.segment_count" class="flex justify-between text-xs">
                <dt class="text-gray-500">Subtitle segments</dt>
                <dd class="text-gray-200 font-mono">{{ job.segment_count }}</dd>
              </div>
              <div v-if="job.output_size_bytes" class="flex justify-between text-xs">
                <dt class="text-gray-500">Output size</dt>
                <dd class="text-gray-200 font-mono">{{ formatBytes(job.output_size_bytes) }}</dd>
              </div>
              <div class="flex justify-between text-xs">
                <dt class="text-gray-500">Duration</dt>
                <dd class="text-gray-200 font-mono">{{ timeElapsed(job.created_at, job.updated_at) }}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
