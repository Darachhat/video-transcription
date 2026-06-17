<script setup lang="ts">
import type { Job } from '~/composables/usePipeline'
import { usePipeline } from '~/composables/usePipeline'

const props = defineProps<{ job: Job }>()
const emit = defineEmits<{ delete: [id: string] }>()

const { formatBytes, formatDate, timeElapsed, getDownloadUrl, stageIndex } = usePipeline()

const progress = computed(() => {
  if (props.job.status === 'DONE') return 100
  if (props.job.status === 'FAILED') return 0
  return Math.round((stageIndex(props.job.status) / 5) * 100)
})

const shortUrl = computed(() => {
  try {
    const u = new URL(props.job.url)
    return u.hostname + u.pathname.slice(0, 30) + (u.pathname.length > 30 ? '…' : '')
  } catch {
    return props.job.url.slice(0, 50) + '…'
  }
})
</script>

<template>
  <div class="bg-surface border border-border rounded-xl p-4 hover:border-gray-600 transition-colors group">
    <!-- Top row -->
    <div class="flex items-start justify-between gap-2 mb-3">
      <div class="flex items-center gap-2 min-w-0">
        <span class="material-symbols-outlined text-gray-500 text-[18px] shrink-0">smart_display</span>
        <p class="text-sm text-gray-300 truncate font-mono" :title="job.url">{{ shortUrl }}</p>
      </div>
      <UiStatusBadge :status="job.status" size="sm" />
    </div>

    <!-- Progress bar -->
    <div class="h-1 bg-panel rounded-full overflow-hidden mb-3">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="job.status === 'DONE' ? 'bg-emerald-500' : job.status === 'FAILED' ? 'bg-red-500' : 'bg-accent'"
        :style="{ width: progress + '%' }"
      />
    </div>

    <!-- Meta row -->
    <div class="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500 mb-4">
      <span class="flex items-center gap-1">
        <span class="material-symbols-outlined text-[11px]">mic</span>
        {{ job.whisper_model }}
      </span>
      <span v-if="job.detected_language" class="flex items-center gap-1">
        <span class="material-symbols-outlined text-[11px]">translate</span>
        {{ job.detected_language }}
      </span>
      <span v-if="job.status === 'DONE' && job.output_size_bytes" class="flex items-center gap-1">
        <span class="material-symbols-outlined text-[11px]">folder</span>
        {{ formatBytes(job.output_size_bytes) }}
      </span>
      <span class="flex items-center gap-1">
        <span class="material-symbols-outlined text-[11px]">schedule</span>
        {{ formatDate(job.created_at) }}
      </span>
    </div>

    <!-- Error -->
    <p v-if="job.status === 'FAILED' && job.error_message" class="text-xs text-red-400 font-mono mb-3 bg-red-500/10 rounded px-2 py-1.5 break-all">
      {{ job.error_message.slice(0, 120) }}{{ job.error_message.length > 120 ? '…' : '' }}
    </p>

    <!-- Actions -->
    <div class="flex items-center gap-2">
      <NuxtLink
        :to="`/jobs/${job.id}`"
        class="flex items-center justify-center w-8 h-8 rounded-lg bg-panel hover:bg-border text-gray-400 hover:text-white transition-colors"
        title="View details"
      >
        <span class="material-symbols-outlined text-[16px]">open_in_new</span>
      </NuxtLink>

      <NuxtLink
        v-if="job.status === 'DONE'"
        :to="`/editor/${job.id}`"
        class="flex items-center justify-center w-8 h-8 rounded-lg bg-[#7c3aed]/15 hover:bg-[#7c3aed]/25 text-[#a78bfa] transition-colors border border-[#7c3aed]/20"
        title="Open in Editor"
      >
        <span class="material-symbols-outlined text-[16px]">movie_edit</span>
      </NuxtLink>

      <a
        v-if="job.status === 'DONE'"
        :href="getDownloadUrl(job.id)"
        class="flex items-center justify-center w-8 h-8 rounded-lg bg-accent hover:bg-accent-hover text-white transition-colors"
        title="Download dubbed video"
        download
      >
        <span class="material-symbols-outlined text-[16px]">download</span>
      </a>

      <button
        class="ml-auto flex items-center gap-1 text-xs px-2 py-1.5 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
        @click="emit('delete', job.id)"
      >
        <span class="material-symbols-outlined text-[14px]">delete</span>
      </button>
    </div>
  </div>
</template>
