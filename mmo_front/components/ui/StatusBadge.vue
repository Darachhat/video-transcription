<script setup lang="ts">
const props = defineProps<{ status: string; size?: 'sm' | 'md' }>()

const config: Record<string, { label: string; class: string; dot: string }> = {
  PENDING:     { label: 'Queued',      class: 'bg-gray-500/15 text-gray-400 border-gray-500/30',     dot: 'bg-gray-400' },
  DOWNLOADING: { label: 'Downloading', class: 'bg-blue-500/15 text-blue-400 border-blue-500/30',     dot: 'bg-blue-400 animate-pulse' },
  TRANSCRIBING:{ label: 'Transcribing',class: 'bg-blue-500/15 text-blue-400 border-blue-500/30',     dot: 'bg-blue-400 animate-pulse' },
  TRANSLATING: { label: 'Translating', class: 'bg-violet-500/15 text-violet-400 border-violet-500/30',dot: 'bg-violet-400 animate-pulse' },
  DUBBING:     { label: 'Dubbing',     class: 'bg-amber-500/15 text-amber-400 border-amber-500/30',  dot: 'bg-amber-400 animate-pulse' },
  DONE:        { label: 'Done',        class: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-400' },
  FAILED:      { label: 'Failed',      class: 'bg-red-500/15 text-red-400 border-red-500/30',        dot: 'bg-red-400' },
}

const c = computed(() => config[props.status] ?? config.PENDING)
const sizeClass = computed(() => props.size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-xs px-2.5 py-1')
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-full border font-medium"
    :class="[c.class, sizeClass]"
  >
    <span class="w-1.5 h-1.5 rounded-full shrink-0" :class="c.dot" />
    {{ c.label }}
  </span>
</template>
