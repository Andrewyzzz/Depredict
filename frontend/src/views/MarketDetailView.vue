<template>
  <div class="max-w-6xl mx-auto px-6 py-10 font-body">

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center min-h-[60vh]">
      <div class="text-center">
        <div class="w-10 h-10 rounded-full border-2 border-primary/20 border-t-primary animate-spin mx-auto mb-4"></div>
        <p class="text-on-surface-variant text-sm uppercase tracking-widest font-label">Loading market data...</p>
      </div>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center min-h-[60vh]">
      <div class="max-w-md px-6 py-5 bg-error-container/20 border border-error/20 rounded-xl text-error text-sm">
        <div class="flex items-center gap-2 mb-2">
          <span class="material-symbols-outlined text-lg">error</span>
          <span class="font-bold uppercase tracking-widest text-xs">Error</span>
        </div>
        {{ error }}
      </div>
    </div>

    <!-- Market Detail -->
    <template v-else-if="market">
      <!-- Header -->
      <header class="mb-10">
        <div class="flex items-center gap-3 mb-4">
          <router-link to="/scan" class="text-on-surface-variant hover:text-on-surface transition-colors">
            <span class="material-symbols-outlined text-lg">arrow_back</span>
          </router-link>
          <span
            class="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border"
            :class="categoryTagClass"
          >{{ market.category || 'General' }}</span>
          <span class="text-on-surface-variant text-xs">Source: Polymarket</span>
        </div>
        <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
          <h1 class="text-3xl lg:text-4xl font-headline font-bold text-on-surface tracking-tight leading-tight max-w-3xl">
            {{ market.question }}
          </h1>
          <div class="text-right shrink-0">
            <span class="micro-label block mb-1">Current Probability</span>
            <div class="text-6xl lg:text-7xl font-headline font-bold text-primary tabular-nums tracking-tighter">
              {{ (market.market_price * 100).toFixed(1) }}%
            </div>
          </div>
        </div>
        <div class="flex items-center gap-6 mt-4 text-sm text-on-surface-variant">
          <div v-if="formattedEndDate" class="flex items-center gap-1.5">
            <span class="material-symbols-outlined text-base">event</span>
            Ends {{ formattedEndDate }}
          </div>
        </div>
      </header>

      <!-- Main Grid: Chart + Analysis Panel -->
      <div class="grid grid-cols-1 lg:grid-cols-10 gap-6 mb-8">
        <!-- Price Chart -->
        <div class="lg:col-span-7 bg-surface-container rounded-xl p-6">
          <div class="flex items-center justify-between mb-6">
            <h3 class="font-headline font-bold text-on-surface text-sm uppercase tracking-wider">Probability Trend</h3>
            <div class="flex gap-1">
              <button
                v-for="opt in intervalOptions"
                :key="opt.value"
                class="px-3 py-1 rounded text-xs font-bold uppercase tracking-wider transition-all"
                :class="selectedInterval === opt.value
                  ? 'bg-primary-container text-on-primary-container'
                  : 'text-on-surface-variant hover:text-on-surface'"
                @click="changeInterval(opt.value)"
              >{{ opt.label }}</button>
            </div>
          </div>
          <div class="h-72" v-if="chartData">
            <Line :data="chartData" :options="chartOptions" />
          </div>
          <div v-else-if="historyLoading" class="h-72 flex items-center justify-center">
            <div class="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin"></div>
          </div>
          <div v-else class="h-72 flex items-center justify-center text-on-surface-variant text-sm">
            No price history available
          </div>
        </div>

        <!-- Right Panel: Analyze -->
        <div class="lg:col-span-3 space-y-4">
          <div class="bg-surface-container rounded-xl p-6">
            <span class="px-2 py-0.5 bg-primary/10 text-primary text-[10px] font-bold uppercase tracking-widest rounded border border-primary/20">AI Analysis</span>
            <h3 class="font-headline font-bold text-on-surface text-lg mt-3 mb-2">Multi-Agent Debate</h3>
            <p class="text-sm text-on-surface-variant leading-relaxed mb-6">
              Run our multi-agent debate engine to generate an independent probability estimate and compare it against the market.
            </p>
            <button
              @click="runAnalysis"
              :disabled="analyzing"
              class="w-full py-3 rounded-xl bg-primary-container text-on-primary-container font-headline font-bold uppercase tracking-widest text-sm hover:brightness-110 active:scale-[0.98] transition-all shadow-[0_0_20px_rgba(77,142,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              <span class="material-symbols-outlined text-lg">bolt</span>
              {{ analyzing ? 'Starting...' : 'Run Quantitative Analysis' }}
            </button>
          </div>

          <!-- Market Rules -->
          <div v-if="market.description" class="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10">
            <h4 class="micro-label mb-3">Market Rules</h4>
            <p class="text-xs text-on-surface-variant leading-relaxed line-clamp-6">{{ market.description }}</p>
          </div>
        </div>
      </div>

      <!-- Stats Row -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
          <span class="micro-label">24h Volume</span>
          <div class="text-2xl font-headline font-bold mt-1 tabular-nums text-on-surface">${{ formatVolume(market.volume_24h) }}</div>
        </div>
        <div class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
          <span class="micro-label">Total Liquidity</span>
          <div class="text-2xl font-headline font-bold mt-1 tabular-nums text-on-surface">${{ formatVolume(market.liquidity) }}</div>
        </div>
        <div class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
          <span class="micro-label">Outcomes</span>
          <div class="text-lg font-headline font-bold mt-1 text-on-surface">
            <span v-for="(o, i) in market.outcomes" :key="i">
              {{ o }}<span v-if="i < market.outcomes.length - 1" class="text-on-surface-variant"> / </span>
            </span>
          </div>
        </div>
        <div class="bg-surface-container-low rounded-xl p-5 border border-outline-variant/10">
          <span class="micro-label">Status</span>
          <div class="text-lg font-headline font-bold mt-1 text-secondary flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-secondary shadow-[0_0_8px_rgba(74,225,118,0.5)]"></span>
            Active
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend, Filler,
} from 'chart.js'
import api from '../api/client'
import { useDebateStore } from '../store/index'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler)

const route = useRoute()
const router = useRouter()
const store = useDebateStore()

const market = ref(null)
const loading = ref(true)
const error = ref(null)
const analyzing = ref(false)

const priceHistory = ref([])
const historyLoading = ref(false)
const selectedInterval = ref('1w')
const intervalOptions = [
  { label: '1D', value: '1d' },
  { label: '7D', value: '1w' },
  { label: '30D', value: '1m' },
]

const formattedEndDate = computed(() => {
  const d = market.value?.end_date
  if (!d) return ''
  try {
    const date = new Date(d)
    if (isNaN(date.getTime())) return ''
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  } catch { return '' }
})

const categoryTagClass = computed(() => {
  const cat = (market.value?.category || '').toLowerCase()
  const map = {
    politics: 'bg-primary/10 text-primary border-primary/20',
    crypto: 'bg-primary/10 text-primary border-primary/20',
    sports: 'bg-secondary/10 text-secondary border-secondary/20',
    'science & tech': 'bg-secondary/10 text-secondary border-secondary/20',
    economics: 'bg-tertiary/10 text-tertiary border-tertiary/20',
    entertainment: 'bg-tertiary/10 text-tertiary border-tertiary/20',
  }
  return map[cat] || 'bg-on-surface-variant/10 text-on-surface-variant border-on-surface-variant/20'
})

const chartData = computed(() => {
  if (!priceHistory.value.length) return null
  const points = priceHistory.value
  const labels = points.map(p => {
    const d = new Date(p.t * 1000)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
  })
  const data = points.map(p => (p.p * 100))

  return {
    labels,
    datasets: [{
      label: 'Probability',
      data,
      borderColor: '#4d8eff',
      backgroundColor: 'rgba(77, 142, 255, 0.08)',
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBackgroundColor: '#4d8eff',
      pointHoverBorderColor: '#111317',
      pointHoverBorderWidth: 2,
      fill: true,
      tension: 0.3,
    }],
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#1e2024',
      titleColor: '#c2c6d6',
      bodyColor: '#e2e2e8',
      borderColor: 'rgba(255,255,255,0.06)',
      borderWidth: 1,
      padding: 12,
      displayColors: false,
      callbacks: {
        label: (ctx) => `${ctx.parsed.y.toFixed(1)}%`,
      },
    },
  },
  scales: {
    x: {
      grid: { color: 'rgba(66,71,84,0.15)' },
      ticks: {
        color: '#8c909f',
        maxTicksLimit: 6,
        maxRotation: 0,
        font: { size: 10 },
      },
    },
    y: {
      min: 0,
      max: 100,
      grid: { color: 'rgba(66,71,84,0.15)' },
      ticks: {
        color: '#8c909f',
        callback: (v) => v + '%',
        font: { size: 10 },
      },
    },
  },
}

function formatVolume(vol) {
  if (vol == null) return '--'
  if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(1) + 'M'
  if (vol >= 1_000) return (vol / 1_000).toFixed(1) + 'K'
  return vol.toFixed(0)
}

async function fetchMarket() {
  loading.value = true
  error.value = null
  const slug = route.params.slug
  try {
    const res = await api.get(`/api/market/${slug}/price`)
    market.value = res.data
    fetchHistory()
  } catch (err) {
    error.value = err.response?.data?.error || 'Failed to load market'
  } finally {
    loading.value = false
  }
}

async function fetchHistory() {
  historyLoading.value = true
  const slug = route.params.slug
  const fidelityMap = { '1d': 5, '1w': 60, '1m': 360 }
  try {
    const res = await api.get(`/api/market/${slug}/history`, {
      params: {
        interval: selectedInterval.value,
        fidelity: fidelityMap[selectedInterval.value] || 60,
      },
    })
    priceHistory.value = res.data.history || []
  } catch {
    priceHistory.value = []
  } finally {
    historyLoading.value = false
  }
}

function changeInterval(val) {
  selectedInterval.value = val
  fetchHistory()
}

async function runAnalysis() {
  if (!market.value) return
  analyzing.value = true
  try {
    const m = market.value
    await store.startDebate(m.question, m.market_price, m.slug, m.end_date || null)
    router.push('/analyze')
  } catch {
    analyzing.value = false
  }
}

onMounted(fetchMarket)
</script>
