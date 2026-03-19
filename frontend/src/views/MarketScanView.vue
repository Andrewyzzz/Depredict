<template>
  <div class="flex flex-col gap-6 p-6">
    <!-- Page Header -->
    <div class="flex justify-between items-start gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-headline font-bold text-on-surface tracking-tight">Market Scanner</h1>
        <p class="mt-1 text-sm text-on-surface-variant">Find mispriced Polymarket contracts</p>
      </div>
      <button
        class="inline-flex items-center gap-2 px-4 py-2.5 bg-surface-container-highest/50 hover:bg-surface-container-highest text-primary-container rounded-lg border border-primary-container/20 transition-all duration-200 font-headline text-xs font-bold uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed"
        @click="fetchMarkets"
        :disabled="loading"
      >
        <span v-if="!loading" class="material-symbols-outlined text-sm">refresh</span>
        {{ loading ? 'Scanning...' : 'Refresh Markets' }}
      </button>
    </div>

    <!-- Search + Category Filter Pills -->
    <div class="flex flex-col gap-4">
      <div class="relative max-w-sm">
        <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-lg pointer-events-none">search</span>
        <input
          v-model="searchQuery"
          type="text"
          class="w-full pl-10 pr-4 py-2.5 bg-surface-container border border-outline-variant/40 rounded-lg text-sm text-on-surface placeholder-on-surface-variant/60 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all font-body"
          placeholder="Search markets..."
        />
      </div>
      <div class="flex flex-wrap items-center gap-2 overflow-x-auto pb-2">
        <button
          v-for="cat in categories"
          :key="cat"
          class="px-5 py-2 rounded-full font-headline text-xs font-medium transition-all whitespace-nowrap"
          :class="activeCategory === cat
            ? 'bg-primary-container text-on-primary-container font-bold shadow-[0_0_15px_rgba(77,142,255,0.3)]'
            : 'border border-outline-variant/40 text-on-surface-variant hover:border-primary/40 hover:text-on-surface'"
          @click="activeCategory = cat"
        >
          {{ cat }}
        </button>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="error" class="px-4 py-3 rounded-lg bg-error-container/20 border border-error/30 text-error text-sm font-body">
      {{ error }}
    </div>

    <!-- Loading State: Skeleton Cards -->
    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="i in 6"
        :key="'skel-' + i"
        class="glass-card rounded-xl p-5 flex flex-col h-full border-dashed border-outline-variant/30 bg-white/[0.01]"
      >
        <div class="flex justify-between items-start mb-4 animate-pulse">
          <div class="w-16 h-4 bg-surface-container-highest rounded"></div>
          <div class="w-12 h-4 bg-surface-container-highest rounded"></div>
        </div>
        <div class="space-y-3 mb-6 animate-pulse">
          <div class="w-full h-4 bg-surface-container-highest rounded"></div>
          <div class="w-4/5 h-4 bg-surface-container-highest rounded"></div>
        </div>
        <div class="mt-auto animate-pulse">
          <div class="flex items-end justify-between mb-4">
            <div class="space-y-2">
              <div class="w-20 h-2 bg-surface-container-highest rounded"></div>
              <div class="w-24 h-8 bg-surface-container-highest rounded"></div>
            </div>
            <div class="space-y-2 flex flex-col items-end">
              <div class="w-12 h-2 bg-surface-container-highest rounded"></div>
              <div class="w-16 h-4 bg-surface-container-highest rounded"></div>
            </div>
          </div>
          <div class="w-full h-10 bg-surface-container-highest/50 rounded-lg"></div>
        </div>
      </div>
    </div>

    <!-- Market Cards Grid -->
    <div v-else-if="filteredMarkets.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="market in filteredMarkets"
        :key="market.id"
        class="glass-card rounded-xl p-5 flex flex-col h-full group"
      >
        <!-- Top row: category tag + edge trend -->
        <div class="flex justify-between items-start mb-4">
          <span
            class="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border"
            :class="categoryTagClass(market.category)"
          >
            {{ market.category || 'General' }}
          </span>
          <div
            v-if="market.edge != null"
            class="flex items-center gap-1 text-xs tabular-nums font-medium"
            :class="market.edge > 0 ? 'text-secondary' : market.edge < 0 ? 'text-tertiary' : 'text-on-surface-variant'"
          >
            <span class="material-symbols-outlined text-sm">
              {{ market.edge > 0 ? 'trending_up' : market.edge < 0 ? 'trending_down' : 'trending_flat' }}
            </span>
            {{ market.edge > 0 ? '+' : '' }}{{ (market.edge * 100).toFixed(1) }}%
          </div>
          <div v-else class="text-xs text-on-surface-variant/50">--</div>
        </div>

        <!-- Question -->
        <h3 class="text-on-surface font-headline font-medium text-base mb-6 line-clamp-2 min-h-[3rem]">
          {{ market.question }}
        </h3>

        <!-- Bottom section: price, volume, analyze button -->
        <div class="mt-auto">
          <div class="flex items-end justify-between mb-4">
            <div>
              <p class="text-[10px] text-on-surface-variant uppercase tracking-widest mb-1">Market Price</p>
              <p class="text-3xl font-headline font-black text-on-surface tabular-nums">
                {{ market.market_price != null ? (market.market_price * 100).toFixed(1) + '%' : '--' }}
              </p>
            </div>
            <div class="text-right">
              <p class="text-[10px] text-on-surface-variant uppercase tracking-widest mb-1">24h Vol</p>
              <p class="text-sm font-medium text-on-surface tabular-nums">
                <span v-if="market.volume_24h != null">${{ formatVolume(market.volume_24h) }}</span>
                <span v-else class="text-on-surface-variant/50">--</span>
              </p>
            </div>
          </div>
          <button
            class="w-full py-2.5 rounded-lg border border-primary-container/30 text-primary hover:bg-primary-container/10 transition-all font-headline text-xs font-bold uppercase tracking-widest disabled:opacity-50 disabled:cursor-not-allowed"
            @click="analyzeMarket(market)"
            :disabled="market.analyzing"
          >
            {{ market.analyzing ? 'Analyzing...' : 'Analyze' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="!loading" class="flex flex-col items-center py-16 text-center">
      <span class="material-symbols-outlined text-5xl text-on-surface-variant/40 mb-4">search_off</span>
      <p class="text-base font-headline font-semibold text-on-surface mb-1">No markets found</p>
      <p class="text-sm text-on-surface-variant max-w-xs">
        Try adjusting your search or filters, or click <strong class="text-primary">Refresh Markets</strong> to scan.
      </p>
    </div>

    <!-- Footer Meta -->
    <div v-if="!loading && filteredMarkets.length" class="mt-6 pt-6 border-t border-outline-variant/10 flex flex-col md:flex-row justify-between items-center gap-4 text-on-surface-variant">
      <div class="flex items-center gap-6">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-secondary shadow-[0_0_8px_rgba(74,225,118,0.5)]"></span>
          <span class="text-[10px] uppercase font-bold tracking-widest">Oracle Node: Active</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-sm">bolt</span>
          <span class="text-[10px] uppercase font-bold tracking-widest tabular-nums">{{ filteredMarkets.length }} Markets</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'
import { useDebateStore } from '../store/index'

const router = useRouter()
const store = useDebateStore()
const markets = ref([])
const loading = ref(false)
const error = ref(null)
const searchQuery = ref('')
const activeCategory = ref('All')

const categories = ['All', 'Politics', 'Crypto', 'Sports', 'Science & Tech', 'Economics', 'Entertainment', 'Other']

const sortedMarkets = computed(() => {
  return [...markets.value].sort((a, b) => {
    const edgeA = Math.abs(a.edge ?? 0)
    const edgeB = Math.abs(b.edge ?? 0)
    return edgeB - edgeA
  })
})

const filteredMarkets = computed(() => {
  let list = sortedMarkets.value

  if (activeCategory.value !== 'All') {
    list = list.filter((m) => {
      const cat = (m.category || 'General').toLowerCase()
      return cat === activeCategory.value.toLowerCase()
    })
  }

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter((m) => (m.question || '').toLowerCase().includes(q))
  }

  return list
})

function categoryTagClass(category) {
  const cat = (category || '').toLowerCase()
  const map = {
    politics: 'bg-primary/10 text-primary border-primary/20',
    crypto: 'bg-primary/10 text-primary border-primary/20',
    sports: 'bg-secondary/10 text-secondary border-secondary/20',
    'science & tech': 'bg-secondary-fixed-dim/10 text-secondary-fixed-dim border-secondary-fixed-dim/20',
    economics: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    entertainment: 'bg-tertiary-fixed-dim/10 text-tertiary-fixed-dim border-tertiary-fixed-dim/20',
    other: 'bg-on-surface-variant/10 text-on-surface-variant border-on-surface-variant/20',
  }
  return map[cat] || 'bg-on-surface-variant/10 text-on-surface-variant border-on-surface-variant/20'
}

function formatVolume(vol) {
  if (vol == null) return '--'
  if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M'
  if (vol >= 1_000) return (vol / 1_000).toFixed(1) + 'K'
  return vol.toString()
}

async function fetchMarkets() {
  loading.value = true
  error.value = null
  try {
    const response = await api.get('/api/market/scan')
    markets.value = (response.data.markets || []).map((m) => ({
      ...m,
      analyzing: false,
    }))
  } catch (err) {
    error.value = err.response?.data?.error || 'Failed to fetch markets'
  } finally {
    loading.value = false
  }
}

async function analyzeMarket(market) {
  market.analyzing = true
  try {
    const result = await store.startDebate(market.question, market.market_price, market.slug)
    if (result?.task_id) {
      router.push('/analyze')
    }
  } catch {
    market.analyzing = false
  }
}

onMounted(fetchMarkets)
</script>
