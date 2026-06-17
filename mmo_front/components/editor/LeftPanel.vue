<script setup lang="ts">
import { EDITOR_KEY } from '~/composables/useEditorState'

const editor = inject(EDITOR_KEY)!

// ── Image upload ────────────────────────────────────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null)

function triggerImageUpload() {
  fileInput.value?.click()
}

function onFileChange(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files) return
  for (const file of Array.from(files)) {
    if (file.type.startsWith('image/')) editor.addImageOverlay(file)
  }
  // reset so same file can be re-uploaded
  if (fileInput.value) fileInput.value.value = ''
}

const tabs = [
  { id: 'media',   label: 'Media',   icon: 'perm_media' },
  { id: 'audio',   label: 'Audio',   icon: 'music_note' },
  { id: 'text',    label: 'Text',    icon: 'text_fields' },
  { id: 'sticker', label: 'Sticker', icon: 'emoji_emotions' },
] as const
</script>

<template>
  <!-- 280px fixed left panel -->
  <aside class="w-[260px] shrink-0 flex flex-col bg-[#111] border-r border-[#2a2a2a]">
    <!-- Tab bar -->
    <div class="flex border-b border-[#2a2a2a] shrink-0">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="flex-1 flex items-center justify-center py-3 transition-colors relative"
        :class="editor.activeTab.value === tab.id
          ? 'text-[#7c3aed]'
          : 'text-gray-600 hover:text-gray-300'"
        :title="tab.label"
        @click="editor.activeTab.value = tab.id"
      >
        <span class="material-symbols-outlined text-[20px]">{{ tab.icon }}</span>
        <!-- Active underline -->
        <span
          v-if="editor.activeTab.value === tab.id"
          class="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-[#7c3aed]"
        />
      </button>
    </div>

    <!-- Panel body -->
    <div class="flex-1 overflow-y-auto">

      <!-- MEDIA tab -->
      <div v-if="editor.activeTab.value === 'media'" class="p-3 space-y-3">
        <!-- Hidden file input -->
        <input
          ref="fileInput"
          type="file"
          accept="image/*"
          multiple
          class="hidden"
          @change="onFileChange"
        />

        <!-- Upload image button -->
        <button
          class="w-full flex items-center justify-center gap-2 py-2 border border-dashed border-[#3a3a3a] rounded-lg text-xs text-gray-400 hover:border-[#7c3aed] hover:text-[#7c3aed] transition-colors"
          @click="triggerImageUpload"
        >
          <span class="material-symbols-outlined text-[16px]">add_photo_alternate</span>
          Add Image / Logo
        </button>

        <!-- Dubbed video loaded -->
        <div
          v-if="editor.videoUrl.value"
          class="rounded-lg border border-[#2a2a2a] overflow-hidden cursor-pointer hover:border-[#7c3aed] transition-colors group"
          @click="editor.selectClip(null)"
        >
          <div class="bg-[#1a1a1a] aspect-video flex items-center justify-center relative">
            <span class="material-symbols-outlined text-[32px] text-gray-600 group-hover:text-[#7c3aed] transition-colors">smart_display</span>
            <div class="absolute inset-0 flex items-end p-1.5">
              <span class="text-[9px] text-gray-400 font-mono bg-black/60 px-1 rounded">Dubbed Output</span>
            </div>
          </div>
        </div>

        <div v-else class="flex flex-col items-center py-4 text-center gap-2">
          <span class="material-symbols-outlined text-[36px] text-gray-600">add_photo_alternate</span>
          <p class="text-xs text-gray-500">No images added</p>
          <p class="text-[10px] text-gray-600">Upload logos, watermarks or sponsor images</p>
        </div>

        <!-- Uploaded image overlays list -->
        <div v-if="editor.imageOverlays.value.length > 0" class="space-y-1.5">
          <p class="text-[10px] text-gray-500 uppercase tracking-wider">Overlays</p>
          <div
            v-for="img in editor.imageOverlays.value"
            :key="img.id"
            class="flex items-center gap-2 p-1.5 rounded-lg border cursor-pointer transition-all"
            :class="editor.selectedImageId.value === img.id
              ? 'border-[#7c3aed] bg-[#7c3aed]/10'
              : 'border-[#2a2a2a] hover:border-[#3a3a3a]'"
            @click="editor.selectImage(img.id)"
          >
            <!-- Thumbnail -->
            <div class="w-10 h-10 rounded bg-[#0a0a0a] shrink-0 overflow-hidden flex items-center justify-center border border-[#2a2a2a]">
              <img :src="img.src" class="max-w-full max-h-full object-contain" />
            </div>
            <!-- Name + opacity -->
            <div class="flex-1 min-w-0">
              <p class="text-[10px] text-gray-200 truncate">{{ img.name }}</p>
              <p class="text-[9px] text-gray-500">{{ Math.round(img.opacity * 100) }}% opacity</p>
            </div>
            <!-- Delete -->
            <button
              class="text-gray-600 hover:text-red-400 transition-colors p-0.5"
              title="Remove overlay"
              @click.stop="editor.deleteImageOverlay(img.id)"
            >
              <span class="material-symbols-outlined text-[14px]">close</span>
            </button>
          </div>
        </div>
      </div>

      <!-- AUDIO tab -->
      <div v-else-if="editor.activeTab.value === 'audio'" class="p-3">
        <div class="flex flex-col items-center py-8 text-center gap-2">
          <span class="material-symbols-outlined text-[36px] text-gray-600">music_note</span>
          <p class="text-xs text-gray-500">Audio tracks</p>
          <p class="text-[10px] text-gray-600">Dubbed audio is included with the video</p>
        </div>

        <!-- Audio track info -->
        <div v-if="editor.videoUrl.value" class="mt-2 rounded-lg border border-[#2a2a2a] p-3">
          <div class="flex items-center gap-2">
            <span class="material-symbols-outlined text-[16px] text-emerald-400">graphic_eq</span>
            <div>
              <p class="text-xs text-gray-200">Dubbed Audio (Khmer)</p>
              <p class="text-[10px] text-gray-500 font-mono">km-KH-PisethNeural · AAC 192k</p>
            </div>
          </div>
        </div>
      </div>

      <!-- TEXT tab -->
      <div v-else-if="editor.activeTab.value === 'text'" class="p-3 space-y-2">
        <button
          class="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg bg-[#7c3aed]/15 border border-[#7c3aed]/30 text-[#a78bfa] text-xs font-medium hover:bg-[#7c3aed]/25 transition-colors"
          @click="editor.addTextClip()"
        >
          <span class="material-symbols-outlined text-[16px]">add</span>
          Add Text Overlay
        </button>

        <!-- Preset text styles -->
        <p class="text-[10px] text-gray-500 pt-2 uppercase tracking-wider">Presets</p>
        <div class="space-y-1.5">
          <button
            v-for="preset in [
              { label: 'Title', size: 36, bold: true },
              { label: 'Subtitle', size: 24, bold: false },
              { label: 'Caption', size: 18, bold: false },
              { label: 'Lower Third', size: 20, bold: true },
            ]"
            :key="preset.label"
            class="w-full text-left px-3 py-2 rounded-lg border border-[#2a2a2a] hover:border-[#7c3aed] hover:bg-[#7c3aed]/10 transition-colors cursor-pointer"
            @click="editor.addTextClip()"
          >
            <p class="text-xs text-gray-200" :style="{ fontSize: Math.min(preset.size * 0.45, 14) + 'px', fontWeight: preset.bold ? 600 : 400 }">
              {{ preset.label }}
            </p>
            <p class="text-[9px] text-gray-500 mt-0.5">{{ preset.size }}px {{ preset.bold ? '· Bold' : '' }}</p>
          </button>
        </div>
      </div>

      <!-- STICKER tab -->
      <div v-else-if="editor.activeTab.value === 'sticker'" class="p-3">
        <div class="flex flex-col items-center py-8 gap-2">
          <span class="material-symbols-outlined text-[36px] text-gray-600">emoji_emotions</span>
          <p class="text-xs text-gray-500">Stickers</p>
          <p class="text-[10px] text-gray-600 text-center">Sticker library coming soon</p>
        </div>

        <!-- Icon sticker grid -->
        <div class="grid grid-cols-5 gap-1.5">
          <button
            v-for="item in [
              { icon: 'movie',                 title: 'Movie'       },
              { icon: 'music_note',            title: 'Music'       },
              { icon: 'star',                  title: 'Star'        },
              { icon: 'favorite',              title: 'Heart'       },
              { icon: 'local_fire_department', title: 'Fire'        },
              { icon: 'thumb_up',              title: 'Thumbs up'   },
              { icon: 'sentiment_satisfied',   title: 'Happy'       },
              { icon: 'gps_fixed',             title: 'Target'      },
              { icon: 'auto_awesome',          title: 'Sparkle'     },
              { icon: 'theaters',              title: 'Clapper'     },
            ]"
            :key="item.icon"
            :title="item.title"
            class="aspect-square flex items-center justify-center rounded-lg border border-[#2a2a2a] hover:border-[#7c3aed] hover:bg-[#7c3aed]/10 transition-colors"
          >
            <span class="material-symbols-outlined text-[18px] text-gray-400">{{ item.icon }}</span>
          </button>
        </div>
      </div>

    </div>
  </aside>
</template>
