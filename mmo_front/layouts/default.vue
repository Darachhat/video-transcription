<script setup lang="ts">
const route = useRoute()

const navItems = [
  { name: 'Dashboard', href: '/', icon: 'dashboard' },
  { name: 'Jobs', href: '/jobs', icon: 'video_library' },
]

const mobileOpen = ref(false)
watch(() => route.path, () => { mobileOpen.value = false })
</script>

<template>
  <div class="flex min-h-screen bg-[#0a0a0a]">
    <!-- ── Desktop Sidebar ─────────────────────────────────── -->
    <aside class="hidden lg:flex flex-col fixed left-0 top-0 h-screen w-[220px] bg-panel border-r border-border z-40">
      <!-- Logo -->
      <div class="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div class="w-8 h-8 rounded-lg bg-accent flex items-center justify-center shrink-0">
          <span class="text-white text-sm font-bold">M</span>
        </div>
        <div>
          <p class="text-white font-semibold text-sm leading-none">MMO Dub</p>
          <p class="text-gray-500 text-xs mt-0.5">Studio</p>
        </div>
      </div>

      <!-- Nav -->
      <nav class="flex-1 px-3 py-4 space-y-1">
        <NuxtLink
          v-for="item in navItems"
          :key="item.href"
          :to="item.href"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150"
          :class="route.path === item.href
            ? 'bg-accent-muted text-accent border border-accent/30'
            : 'text-gray-400 hover:text-gray-100 hover:bg-surface'"
        >
          <span class="material-symbols-outlined text-[18px]">{{ item.icon }}</span>
          {{ item.name }}
        </NuxtLink>
      </nav>

      <!-- Footer -->
      <div class="px-5 py-4 border-t border-border">
        <p class="text-gray-600 text-xs font-mono">v1.0.0 · mmo-tool</p>
      </div>
    </aside>

    <!-- ── Mobile Header ───────────────────────────────────── -->
    <header class="lg:hidden fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-3 bg-panel border-b border-border">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-md bg-accent flex items-center justify-center">
          <span class="text-white text-xs font-bold">M</span>
        </div>
        <span class="text-white font-semibold text-sm">MMO Dub Studio</span>
      </div>
      <button
        class="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-surface transition-colors"
        @click="mobileOpen = !mobileOpen"
      >
        <span class="material-symbols-outlined text-xl">{{ mobileOpen ? 'close' : 'menu' }}</span>
      </button>
    </header>

    <!-- Mobile Drawer -->
    <Transition name="drawer">
      <div v-if="mobileOpen" class="lg:hidden fixed inset-0 z-40" @click.self="mobileOpen = false">
        <div class="absolute left-0 top-0 h-full w-64 bg-panel border-r border-border pt-16">
          <nav class="px-3 py-4 space-y-1">
            <NuxtLink
              v-for="item in navItems"
              :key="item.href"
              :to="item.href"
              class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
              :class="route.path === item.href
                ? 'bg-accent-muted text-accent border border-accent/30'
                : 'text-gray-400 hover:text-gray-100 hover:bg-surface'"
            >
              <span class="material-symbols-outlined text-[18px]">{{ item.icon }}</span>
              {{ item.name }}
            </NuxtLink>
          </nav>
        </div>
      </div>
    </Transition>

    <!-- ── Main Content ────────────────────────────────────── -->
    <main class="flex-1 lg:ml-[220px] pt-14 lg:pt-0 min-h-screen">
      <slot />
    </main>
  </div>

  <!-- Fonts are loaded globally via nuxt.config.ts app.head.link -->
</template>

<style scoped>
.drawer-enter-active, .drawer-leave-active { transition: opacity 0.2s ease; }
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
</style>
