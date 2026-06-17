<script setup lang="ts">
import type { Job } from '~/composables/usePipeline'
import { usePipeline } from '~/composables/usePipeline'

const { listJobs, waitForJobUpdate, deleteJob } = usePipeline()

const jobs = ref<Job[]>([])
const loadError = ref('')
const loading = ref(true)

async function loadJobs() {
  try {
    jobs.value = await listJobs()
  } catch (e: any) {
    loadError.value = e?.message || 'Could not load jobs.'
  } finally {
    loading.value = false
  }
}

function onJobSubmitted(job: Job) {
  jobs.value.unshift(job)
  // Kick off long-poll if it exited because there were no active jobs before
  if (!pollActive) startLongPoll()
}

async function onDelete(id: string) {
  try {
    await deleteJob(id)
    jobs.value = jobs.value.filter(j => j.id !== id)
  } catch {}
}

// Long-poll loop: watch the first active job; refresh the full list on any change
let pollActive = false

async function startLongPoll() {
  pollActive = true
  while (pollActive) {
    const activeJob = jobs.value.find(j => !['DONE', 'FAILED'].includes(j.status))
    if (!activeJob) break  // nothing left to watch
    try {
      await waitForJobUpdate(activeJob.id, activeJob.status)
      if (!pollActive) break
      jobs.value = await listJobs().catch(() => jobs.value)
    } catch {
      await new Promise(r => setTimeout(r, 2000))
    }
  }
}

onMounted(async () => {
  await loadJobs()
  startLongPoll()
})

onUnmounted(() => { pollActive = false })

const activeCount = computed(() => jobs.value.filter(j => !['DONE', 'FAILED'].includes(j.status)).length)
const doneCount = computed(() => jobs.value.filter(j => j.status === 'DONE').length)
const failedCount = computed(() => jobs.value.filter(j => j.status === 'FAILED').length)
</script>

<template>
  <div class="min-h-screen p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-white mb-1">Dubbing Studio</h1>
      <p class="text-gray-400 text-sm">Automated video dubbing pipeline — Khmer AI</p>
    </div>

    <!-- Stats row -->
    <div class="grid grid-cols-3 gap-3 mb-8">
      <div class="bg-surface border border-border rounded-xl px-4 py-3">
        <p class="text-xs text-gray-500 mb-1">Processing</p>
        <p class="text-2xl font-bold text-blue-400">{{ activeCount }}</p>
      </div>
      <div class="bg-surface border border-border rounded-xl px-4 py-3">
        <p class="text-xs text-gray-500 mb-1">Completed</p>
        <p class="text-2xl font-bold text-emerald-400">{{ doneCount }}</p>
      </div>
      <div class="bg-surface border border-border rounded-xl px-4 py-3">
        <p class="text-xs text-gray-500 mb-1">Failed</p>
        <p class="text-2xl font-bold text-red-400">{{ failedCount }}</p>
      </div>
    </div>

    <div class="grid lg:grid-cols-[340px_1fr] gap-6">
      <!-- Submit form -->
      <div>
        <SubmitForm @submitted="onJobSubmitted" />
      </div>

      <!-- Job grid -->
      <div>
        <div class="flex items-center justify-between mb-4">
          <h2 class="text-sm font-semibold text-white">
            Jobs
            <span class="ml-2 text-xs text-gray-500 font-normal">({{ jobs.length }} total)</span>
          </h2>
          <button
            class="text-xs text-gray-500 hover:text-white flex items-center gap-1 transition-colors"
            @click="loadJobs"
          >
            <span class="material-symbols-outlined text-[14px]">refresh</span>
            Refresh
          </button>
        </div>

        <!-- Loading -->
        <div v-if="loading" class="grid sm:grid-cols-2 gap-3">
          <div v-for="i in 4" :key="i" class="bg-surface border border-border rounded-xl p-4 animate-pulse">
            <div class="h-4 bg-panel rounded w-3/4 mb-3" />
            <div class="h-1 bg-panel rounded mb-3" />
            <div class="h-3 bg-panel rounded w-1/2" />
          </div>
        </div>

        <!-- Error -->
        <div v-else-if="loadError" class="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
          {{ loadError }}
        </div>

        <!-- Empty -->
        <div v-else-if="jobs.length === 0" class="text-center py-16 text-gray-600">
          <span class="material-symbols-outlined text-5xl block mb-3">video_library</span>
          <p class="text-sm">No jobs yet. Submit a URL to get started.</p>
        </div>

        <!-- Job cards -->
        <div v-else class="grid sm:grid-cols-2 gap-3">
          <JobCard
            v-for="job in jobs"
            :key="job.id"
            :job="job"
            @delete="onDelete"
          />
        </div>
      </div>
    </div>
  </div>
</template>
