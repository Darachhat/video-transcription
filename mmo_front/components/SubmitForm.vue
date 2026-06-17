<script setup lang="ts">
import { usePipeline } from '~/composables/usePipeline'

const emit = defineEmits<{ submitted: [job: any] }>()

const { submitJob } = usePipeline()

const url = ref('')
const whisperModel = ref('base')
const loading = ref(false)
const error = ref('')

const whisperOptions = [
  { value: 'tiny',   label: 'Tiny  — fastest, lower accuracy' },
  { value: 'base',   label: 'Base  — fast, good accuracy' },
  { value: 'small',  label: 'Small — balanced' },
  { value: 'medium', label: 'Medium — slower, high accuracy' },
  { value: 'large',  label: 'Large — slowest, best accuracy' },
]

async function submit() {
  if (!url.value.trim()) { error.value = 'Please enter a video URL.'; return }
  error.value = ''
  loading.value = true
  try {
    const job = await submitJob(url.value.trim(), whisperModel.value)
    url.value = ''
    emit('submitted', job)
  } catch (e: any) {
    error.value = e?.message || 'Failed to submit job.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="bg-surface border border-border rounded-xl p-5">
    <div class="flex items-center gap-2 mb-4">
      <span class="material-symbols-outlined text-accent text-[20px]">add_circle</span>
      <h2 class="text-sm font-semibold text-white">New Dubbing Job</h2>
    </div>

    <form class="space-y-3" @submit.prevent="submit">
      <!-- URL input -->
      <div>
        <label class="block text-xs text-gray-400 mb-1.5">Video URL</label>
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-gray-500 text-[18px]">link</span>
          <input
            v-model="url"
            type="url"
            placeholder="https://www.youtube.com/watch?v=..."
            class="w-full bg-panel border border-border rounded-lg pl-9 pr-4 py-2.5 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/40 transition-colors font-mono"
            :disabled="loading"
          />
        </div>
      </div>

      <!-- Model select -->
      <div>
        <label class="block text-xs text-gray-400 mb-1.5">Whisper Model</label>
        <select
          v-model="whisperModel"
          class="w-full bg-panel border border-border rounded-lg px-3 py-2.5 text-sm text-gray-100 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/40 transition-colors"
          :disabled="loading"
        >
          <option v-for="opt in whisperOptions" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>

      <!-- Error -->
      <p v-if="error" class="text-xs text-red-400 flex items-center gap-1.5">
        <span class="material-symbols-outlined text-[14px]">error</span>
        {{ error }}
      </p>

      <!-- Submit -->
      <button
        type="submit"
        :disabled="loading"
        class="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-accent hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm transition-colors"
      >
        <span v-if="loading" class="material-symbols-outlined text-[16px] animate-spin-slow">progress_activity</span>
        <span v-else class="material-symbols-outlined text-[16px]">rocket_launch</span>
        {{ loading ? 'Submitting…' : 'Start Dubbing' }}
      </button>
    </form>
  </div>
</template>
