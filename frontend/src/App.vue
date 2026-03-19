<template>
  <div class="min-h-screen bg-surface text-on-surface font-body selection:bg-primary-container/30">
    <!-- Top Nav Bar (hidden on homepage which has its own) -->
    <nav v-if="!isHomePage" class="fixed top-0 left-0 w-full z-50 flex items-center justify-between px-6 bg-[#111317]/80 backdrop-blur-xl h-[56px] border-b border-white/10 shadow-[0_0_20px_rgba(59,130,246,0.08)]">
      <div class="flex items-center gap-12">
        <router-link to="/" class="text-xl font-bold text-primary-container tracking-tight font-headline hover:opacity-80 transition-opacity">
          DePredict
        </router-link>
        <div class="hidden md:flex items-center gap-8 h-[56px]">
          <router-link
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="h-full flex items-center text-sm tracking-wide font-headline transition-colors"
            :class="isActive(link.to) ? 'text-primary border-b-2 border-primary-container font-bold' : 'text-on-surface-variant hover:text-on-surface'"
          >
            {{ link.label }}
          </router-link>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <button
          @click="toggleTheme"
          class="p-2 text-on-surface-variant hover:bg-white/5 transition-all duration-200 rounded-full active:scale-95"
        >
          <span class="material-symbols-outlined">{{ themeStore.theme === 'dark' ? 'light_mode' : 'dark_mode' }}</span>
        </button>
      </div>
    </nav>

    <!-- Layout: Sidebar + Content -->
    <div class="flex" :class="isHomePage ? '' : 'pt-[56px]'">
      <!-- Sidebar (not on homepage) -->
      <aside
        v-if="!isHomePage"
        class="hidden md:flex flex-col fixed top-[56px] left-0 w-[220px] h-[calc(100vh-56px)] bg-surface-container-lowest border-r border-white/5 p-5 z-40"
      >
        <div class="mb-8">
          <span class="text-primary-container font-headline font-bold text-sm">DePredict</span>
          <span class="micro-label block mt-0.5 text-on-surface-variant">Quant Terminal</span>
        </div>
        <nav class="flex flex-col gap-1 flex-1">
          <router-link
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
            :class="isActive(link.to)
              ? 'bg-primary-container/10 text-primary border-l-2 border-primary-container'
              : 'text-on-surface-variant hover:bg-white/5 hover:text-on-surface border-l-2 border-transparent'"
          >
            <span class="material-symbols-outlined text-[20px]" :class="isActive(link.to) ? '' : ''">{{ link.icon }}</span>
            {{ link.label }}
          </router-link>
        </nav>
      </aside>

      <!-- Main Content -->
      <main
        :class="isHomePage ? 'w-full' : 'md:ml-[220px] w-full min-h-[calc(100vh-56px)]'"
      >
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from './store'

const route = useRoute()
const themeStore = useThemeStore()

const navLinks = [
  { to: '/analyze', label: 'Analyze', icon: 'terminal' },
  { to: '/scan', label: 'Scanner', icon: 'radar' },
  { to: '/history', label: 'History', icon: 'history' },
]

const isHomePage = computed(() => route.path === '/')

function isActive(path) {
  return route.path.startsWith(path)
}

function toggleTheme() {
  themeStore.toggleTheme()
}
</script>
