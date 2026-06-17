<script setup lang="ts">
import { EDITOR_KEY, DEFAULT_STYLE } from '~/composables/useEditorState'

const editor = inject(EDITOR_KEY)!

const clip  = computed(() => editor.selected.value)
const image = computed(() => editor.selectedImage.value)

function fmtTime(s: number) {
  const m   = Math.floor(s / 60)
  const sec = (s % 60).toFixed(2)
  return `${String(m).padStart(2,'0')}:${sec.padStart(5,'0')}`
}

function parseFmtTime(str: string): number {
  const [m, s] = str.split(':').map(Number)
  return (m || 0) * 60 + (s || 0)
}

const startStr = computed({
  get: () => clip.value ? fmtTime(clip.value.start) : '00:00.00',
  set: (v: string) => { if (clip.value) editor.patchClip(clip.value.id, { start: parseFmtTime(v) }) },
})

const endStr = computed({
  get: () => clip.value ? fmtTime(clip.value.end) : '00:00.00',
  set: (v: string) => { if (clip.value) editor.patchClip(clip.value.id, { end: parseFmtTime(v) }) },
})

const FONT_FAMILIES = [
  'Leelawadee UI', 'Arial', 'Impact', 'Times New Roman',
  'Courier New', 'Georgia', 'Verdana', 'Tahoma',
]

function updateStyle<K extends keyof typeof DEFAULT_STYLE>(key: K, val: typeof DEFAULT_STYLE[K]) {
  if (clip.value) editor.patchStyle(clip.value.id, { [key]: val })
  editor._renderFrame()
}

function updateText(val: string) {
  if (clip.value) editor.patchClip(clip.value.id, { text: val })
  editor._renderFrame()
}
</script>

<template>
  <!-- 260px right properties panel -->
  <aside class="w-[260px] shrink-0 flex flex-col bg-[#111] border-l border-[#2a2a2a] overflow-y-auto">
    <!-- Header -->
    <div class="flex items-center gap-2 px-4 py-3 border-b border-[#2a2a2a] shrink-0">
      <span class="material-symbols-outlined text-[16px] text-gray-400">tune</span>
      <span class="text-xs font-semibold text-gray-300 uppercase tracking-wider">Properties</span>
    </div>

    <!-- No selection -->
    <div v-if="!clip && !image" class="flex-1 flex flex-col items-center justify-center gap-3 text-center px-4">
      <span class="material-symbols-outlined text-[40px] text-gray-700">tune</span>
      <p class="text-xs text-gray-500">Select a clip or image to edit</p>
    </div>

    <!-- ── Image overlay properties ───────────────────────────────────────────────── -->
    <div v-else-if="image" class="flex-1 px-3 py-3 space-y-4">

      <!-- Preview thumbnail -->
      <div class="w-full aspect-video bg-[#0a0a0a] rounded-lg border border-[#2a2a2a] flex items-center justify-center overflow-hidden">
        <img :src="image.src" class="max-w-full max-h-full object-contain" />
      </div>

      <!-- File name -->
      <p class="text-[10px] text-gray-500 truncate" :title="image.name">{{ image.name }}</p>

      <!-- Position -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">open_with</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Position</p>
        </div>
        <div class="space-y-2">
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-500 w-4">X</span>
            <input type="range" min="0" max="95" :value="image.x" class="flex-1 accent-[#7c3aed]"
              @input="editor.updateImageOverlay(image.id, { x: Number(($event.target as HTMLInputElement).value) })" />
            <span class="text-[10px] text-gray-400 w-8 text-right tabular-nums">{{ Math.round(image.x) }}%</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] text-gray-500 w-4">Y</span>
            <input type="range" min="0" max="95" :value="image.y" class="flex-1 accent-[#7c3aed]"
              @input="editor.updateImageOverlay(image.id, { y: Number(($event.target as HTMLInputElement).value) })" />
            <span class="text-[10px] text-gray-400 w-8 text-right tabular-nums">{{ Math.round(image.y) }}%</span>
          </div>
        </div>
      </section>

      <!-- Size -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">photo_size_select_large</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Size</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-[14px] text-gray-500 shrink-0" title="Width">width</span>
          <input type="range" min="5" max="100" :value="image.width" class="flex-1 accent-[#7c3aed]"
            @input="editor.updateImageOverlay(image.id, { width: Number(($event.target as HTMLInputElement).value) })" />
          <span class="text-[10px] text-gray-400 w-8 text-right tabular-nums">{{ Math.round(image.width) }}%</span>
        </div>
      </section>

      <!-- Opacity -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">opacity</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Opacity</p>
        </div>
        <div class="flex items-center gap-2">
          <input type="range" min="0" max="1" step="0.05" :value="image.opacity" class="flex-1 accent-[#7c3aed]"
            @input="editor.updateImageOverlay(image.id, { opacity: Number(($event.target as HTMLInputElement).value) })" />
          <span class="text-[10px] text-gray-400 w-8 text-right tabular-nums">{{ Math.round(image.opacity * 100) }}%</span>
        </div>
      </section>

      <!-- Delete -->
      <button
        class="w-full flex items-center justify-center py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors mt-2"
        title="Remove image overlay"
        @click="editor.deleteImageOverlay(image.id)"
      >
        <span class="material-symbols-outlined text-[16px]">delete</span>
      </button>
    </div>

    <!-- ── Subtitle clip properties ──────────────────────────────────────────────── -->
    <!-- Clip properties -->
    <div v-else class="flex-1 px-3 py-3 space-y-4">

      <!-- Quick-edit button -->
      <button
        class="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg bg-[#7c3aed]/15 border border-[#7c3aed]/30 text-[#a78bfa] text-xs hover:bg-[#7c3aed]/25 transition-colors"
        @click="editor.startInlineEdit(clip.id)"
      >
        <span class="material-symbols-outlined text-[14px]">edit</span>
        Edit on Preview
      </button>




      <!-- Timing section -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">timer</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Timing</p>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="flex items-center gap-1 text-[10px] text-gray-500 mb-1">
              <span class="material-symbols-outlined text-[11px]">play_circle</span> Start
            </label>
            <input
              :value="startStr"
              type="text"
              class="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-gray-100 font-mono focus:outline-none focus:border-[#7c3aed]"
              @change="startStr = ($event.target as HTMLInputElement).value"
            />
          </div>
          <div>
            <label class="flex items-center gap-1 text-[10px] text-gray-500 mb-1">
              <span class="material-symbols-outlined text-[11px]">stop_circle</span> End
            </label>
            <input
              :value="endStr"
              type="text"
              class="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-gray-100 font-mono focus:outline-none focus:border-[#7c3aed]"
              @change="endStr = ($event.target as HTMLInputElement).value"
            />
          </div>
        </div>
      </section>

      <!-- Text content -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">notes</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Content</p>
        </div>
        <textarea
          :value="clip.text"
          rows="3"
          class="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-gray-100 font-mono focus:outline-none focus:border-[#7c3aed] resize-none leading-relaxed"
          @input="updateText(($event.target as HTMLTextAreaElement).value)"
        />
      </section>

      <!-- Font -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">text_format</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Font</p>
        </div>
        <div class="space-y-2">
          <!-- Font family -->
          <select
            :value="clip.style.fontFamily"
            class="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-gray-100 focus:outline-none focus:border-[#7c3aed]"
            @change="updateStyle('fontFamily', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="f in FONT_FAMILIES" :key="f" :value="f">{{ f }}</option>
          </select>

          <!-- Size -->
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[14px] text-gray-500 shrink-0" title="Font size">format_size</span>
            <input
              type="range" min="10" max="80"
              :value="clip.style.fontSize"
              class="flex-1 accent-[#7c3aed]"
              @input="updateStyle('fontSize', Number(($event.target as HTMLInputElement).value))"
            />
            <span class="text-[10px] text-gray-400 w-6 text-right tabular-nums">{{ clip.style.fontSize }}</span>
          </div>

          <!-- Bold / Italic / Underline -->
          <div class="flex gap-1">
            <button
              :class="clip.style.bold
                ? 'bg-[#7c3aed] text-white border-[#7c3aed]'
                : 'bg-transparent text-gray-400 border-[#2a2a2a] hover:border-gray-400'"
              class="flex-1 py-1.5 border rounded text-xs font-bold transition-colors"
              @click="updateStyle('bold', !clip.style.bold)"
            >B</button>
            <button
              :class="clip.style.italic
                ? 'bg-[#7c3aed] text-white border-[#7c3aed]'
                : 'bg-transparent text-gray-400 border-[#2a2a2a] hover:border-gray-400'"
              class="flex-1 py-1.5 border rounded text-xs italic transition-colors"
              @click="updateStyle('italic', !clip.style.italic)"
            >I</button>
            <button
              :class="clip.style.underline
                ? 'bg-[#7c3aed] text-white border-[#7c3aed]'
                : 'bg-transparent text-gray-400 border-[#2a2a2a] hover:border-gray-400'"
              class="flex-1 py-1.5 border rounded text-xs underline transition-colors"
              @click="updateStyle('underline', !clip.style.underline)"
            >U</button>
          </div>

          <!-- Alignment -->
          <div class="flex gap-1">
            <button
              v-for="a in ['left','center','right'] as const"
              :key="a"
              :class="clip.style.align === a
                ? 'bg-[#7c3aed] text-white border-[#7c3aed]'
                : 'bg-transparent text-gray-400 border-[#2a2a2a] hover:border-gray-400'"
              class="flex-1 py-1.5 border rounded transition-colors flex items-center justify-center"
              @click="updateStyle('align', a)"
            >
              <span class="material-symbols-outlined text-[14px]">
                {{ a === 'left' ? 'format_align_left' : a === 'center' ? 'format_align_center' : 'format_align_right' }}
              </span>
            </button>
          </div>
        </div>
      </section>

      <!-- Colors -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">palette</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Colors</p>
        </div>
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="flex items-center gap-1 text-[10px] text-gray-400">
              <span class="material-symbols-outlined text-[12px]">format_color_text</span> Text
            </label>
            <input
              type="color"
              :value="clip.style.color"
              class="w-8 h-6 rounded border border-[#2a2a2a] cursor-pointer bg-transparent"
              @input="updateStyle('color', ($event.target as HTMLInputElement).value)"
            />
          </div>
          <div class="flex items-center justify-between">
            <label class="flex items-center gap-1 text-[10px] text-gray-400">
              <span class="material-symbols-outlined text-[12px]">format_color_fill</span> Background
            </label>
            <div class="flex items-center gap-2">
              <input
                type="color"
                :value="clip.style.bgColor"
                class="w-8 h-6 rounded border border-[#2a2a2a] cursor-pointer bg-transparent"
                @input="updateStyle('bgColor', ($event.target as HTMLInputElement).value)"
              />
              <input
                type="range" min="0" max="1" step="0.05"
                :value="clip.style.bgOpacity"
                class="w-16 accent-[#7c3aed]"
                @input="updateStyle('bgOpacity', Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>
          <div class="flex items-center justify-between">
            <label class="flex items-center gap-1 text-[10px] text-gray-400">
              <span class="material-symbols-outlined text-[12px]">border_color</span> Outline
            </label>
            <div class="flex items-center gap-2">
              <input
                type="color"
                :value="clip.style.outlineColor"
                class="w-8 h-6 rounded border border-[#2a2a2a] cursor-pointer bg-transparent"
                @input="updateStyle('outlineColor', ($event.target as HTMLInputElement).value)"
              />
              <input
                type="range" min="0" max="6" step="0.5"
                :value="clip.style.outlineWidth"
                class="w-16 accent-[#7c3aed]"
                @input="updateStyle('outlineWidth', Number(($event.target as HTMLInputElement).value))"
              />
            </div>
          </div>
        </div>
      </section>

      <!-- Position -->
      <section>
        <div class="flex items-center gap-1.5 mb-2">
          <span class="material-symbols-outlined text-[13px] text-gray-500">swap_vert</span>
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Position</p>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[14px] text-gray-500 shrink-0" title="Vertical position">vertical_align_center</span>
            <input
              type="range" min="5" max="95"
              :value="clip.style.positionY"
              class="flex-1 accent-[#7c3aed]"
              @input="updateStyle('positionY', Number(($event.target as HTMLInputElement).value)); editor._renderFrame()"
            />
            <span class="text-[10px] text-gray-400 w-7 text-right tabular-nums">{{ clip.style.positionY }}%</span>
          </div>
        </div>
      </section>

      <!-- Delete -->
      <button
        class="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors mt-2"
        title="Delete clip"
        @click="editor.deleteClip(clip.id)"
      >
        <span class="material-symbols-outlined text-[16px]">delete</span>
      </button>

    </div>
  </aside>
</template>
