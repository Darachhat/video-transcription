<script setup lang="ts">
import { STAGE_ORDER, STAGE_LABELS } from '~/composables/usePipeline'

const props = defineProps<{
  status: string
  errorMessage?: string | null
}>()

const currentIndex = computed(() => {
  if (props.status === 'FAILED') return -1
  return STAGE_ORDER.indexOf(props.status)
})

const stages = STAGE_ORDER.filter(s => s !== 'PENDING')

function stageState(stage: string): 'done' | 'active' | 'pending' | 'failed' {
  if (props.status === 'FAILED') {
    const stageIdx = STAGE_ORDER.indexOf(stage)
    const currentIdx = currentIndex.value
    if (stageIdx < currentIdx) return 'done'
    if (stageIdx === currentIdx) return 'failed'
    return 'pending'
  }
  const stageIdx = STAGE_ORDER.indexOf(stage)
  if (stageIdx < currentIndex.value) return 'done'
  if (stageIdx === currentIndex.value) return 'active'
  return 'pending'
}
</script>

<template>
  <div class="space-y-1">
    <div
      v-for="(stage, i) in stages"
      :key="stage"
      class="flex items-start gap-3"
    >
      <!-- Line connector -->
      <div class="flex flex-col items-center">
        <!-- Icon -->
        <div
          class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 border transition-all duration-300"
          :class="{
            'bg-emerald-500/20 border-emerald-500 text-emerald-400': stageState(stage) === 'done',
            'bg-blue-500/20 border-blue-500 text-blue-400': stageState(stage) === 'active',
            'bg-surface border-border text-gray-600': stageState(stage) === 'pending',
            'bg-red-500/20 border-red-500 text-red-400': stageState(stage) === 'failed',
          }"
        >
          <span v-if="stageState(stage) === 'done'" class="material-symbols-outlined text-sm">check</span>
          <span v-else-if="stageState(stage) === 'active'" class="material-symbols-outlined text-sm animate-spin-slow">progress_activity</span>
          <span v-else-if="stageState(stage) === 'failed'" class="material-symbols-outlined text-sm">close</span>
          <span v-else class="w-2 h-2 rounded-full bg-gray-600" />
        </div>
        <!-- Connector line -->
        <div
          v-if="i < stages.length - 1"
          class="w-px h-6 mt-1 transition-colors duration-300"
          :class="stageState(stage) === 'done' ? 'bg-emerald-500/40' : 'bg-border'"
        />
      </div>

      <!-- Label -->
      <div class="pb-5 pt-0.5 flex-1 min-w-0">
        <p
          class="text-sm font-medium transition-colors duration-300"
          :class="{
            'text-emerald-400': stageState(stage) === 'done',
            'text-blue-400': stageState(stage) === 'active',
            'text-gray-500': stageState(stage) === 'pending',
            'text-red-400': stageState(stage) === 'failed',
          }"
        >
          {{ STAGE_LABELS[stage] }}
        </p>
        <!-- Active indeterminate bar -->
        <div v-if="stageState(stage) === 'active'" class="mt-1.5 h-0.5 rounded-full bg-surface overflow-hidden w-32">
          <div class="h-full w-1/3 bg-blue-500 rounded-full progress-indeterminate" />
        </div>
        <!-- Error detail -->
        <p v-if="stageState(stage) === 'failed' && errorMessage" class="text-xs text-red-400/80 mt-1 font-mono break-all">
          {{ errorMessage }}
        </p>
      </div>
    </div>
  </div>
</template>
