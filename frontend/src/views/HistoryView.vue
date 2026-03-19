<template>
  <div class="p-6 space-y-6 max-w-[1600px] mx-auto">
    <div v-if="error" class="p-4 bg-error-container/20 border border-error/20 rounded-xl text-error text-sm">{{ error }}</div>

    <!-- Hero Performance Section -->
    <section class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
      <!-- Model Edge Hero -->
      <div class="col-span-2 md:col-span-4 lg:col-span-2 flex flex-col justify-center p-6 glass-panel rounded-xl">
        <span class="micro-label text-on-surface-variant mb-2">Model Edge</span>
        <div
          class="text-4xl lg:text-5xl font-headline font-bold tabular-nums"
          :class="dashEdge > 0 ? 'text-secondary glow-secondary' : dashEdge < 0 ? 'text-tertiary glow-tertiary' : 'text-on-surface-variant'"
        >
          {{ dashEdge != null ? (dashEdge >= 0 ? '+' : '') + dashEdge.toFixed(4) : '--' }}
        </div>
        <p class="text-on-surface-variant text-xs mt-2">
          {{ dashEdge != null ? (dashEdge > 0 ? 'Advantage over markets' : 'Market outperforming') : 'Need resolved data' }}
        </p>
      </div>
      <!-- Stat Cards (compact) -->
      <div class="p-4 bg-surface-container-low rounded-xl border border-outline-variant/10">
        <span class="micro-label text-on-surface-variant">Total</span>
        <div class="text-2xl font-headline font-bold mt-1 tabular-nums">{{ allPredictions.length }}</div>
      </div>
      <div class="p-4 bg-surface-container-low rounded-xl border border-outline-variant/10">
        <span class="micro-label text-on-surface-variant">Resolved</span>
        <div class="text-2xl font-headline font-bold mt-1 tabular-nums text-primary">{{ resolvedPredictions.length }}</div>
      </div>
      <div class="p-4 bg-surface-container-low rounded-xl border border-outline-variant/10">
        <span class="micro-label text-on-surface-variant">Win Rate</span>
        <div class="text-2xl font-headline font-bold mt-1 tabular-nums" :class="winRate > 50 ? 'text-secondary' : ''">
          {{ winRate != null ? winRate.toFixed(1) + '%' : '--' }}
        </div>
      </div>
      <div class="p-4 bg-surface-container-low rounded-xl border border-outline-variant/10">
        <span class="micro-label text-on-surface-variant">Model Brier</span>
        <div class="text-2xl font-headline font-bold mt-1 tabular-nums">{{ dashModelBrier != null ? dashModelBrier.toFixed(4) : '--' }}</div>
      </div>
      <div class="p-4 bg-surface-container-low rounded-xl border border-outline-variant/10">
        <span class="micro-label text-on-surface-variant">Market Brier</span>
        <div class="text-2xl font-headline font-bold mt-1 tabular-nums">{{ dashMarketBrier != null ? dashMarketBrier.toFixed(4) : '--' }}</div>
      </div>
    </section>

    <!-- Visualization Row -->
    <section class="grid grid-cols-1 lg:grid-cols-12 gap-6" v-if="calibrationData.labels.length || allBrierByMethod.length">
      <!-- Calibration Plot (square) -->
      <div class="lg:col-span-5 p-6 bg-surface-container rounded-xl" v-if="calibrationData.labels.length">
        <h3 class="font-headline font-bold text-sm uppercase tracking-wider mb-4 flex items-center gap-2 text-on-surface-variant">
          <span class="material-symbols-outlined text-primary text-lg">analytics</span>
          Calibration Plot
        </h3>
        <div class="w-full" style="aspect-ratio: 1 / 1;">
          <Line :data="calibrationChartData" :options="calibrationChartOptions" />
        </div>
      </div>
      <!-- Brier by Method -->
      <div class="lg:col-span-7 p-6 bg-surface-container rounded-xl" v-if="allBrierByMethod.length">
        <h3 class="font-headline font-bold text-sm uppercase tracking-wider mb-4 flex items-center gap-2 text-on-surface-variant">
          <span class="material-symbols-outlined text-primary text-lg">bar_chart</span>
          Brier Score by Method
        </h3>
        <div class="space-y-4">
          <div v-for="m in sortedAllBrierMethods" :key="m.method" class="space-y-1">
            <div class="flex justify-between text-xs font-label uppercase tracking-wider text-on-surface-variant">
              <span>{{ m.method }}</span>
              <span class="tabular-nums font-bold" :class="m.isBest ? 'text-secondary' : ''">{{ m.score.toFixed(4) }}</span>
            </div>
            <div class="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="m.isMarket ? 'bg-tertiary/60' : 'bg-gradient-to-r from-primary to-primary-container'"
                :style="{ width: brierBarWidth(m.score) }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Live Predictions -->
    <section class="bg-surface-container rounded-xl overflow-hidden" v-if="pendingPredictions.length">
      <div class="p-6 border-b border-outline-variant/10 flex justify-between items-center">
        <h3 class="font-headline font-bold text-lg">Live Predictions</h3>
        <div class="flex items-center gap-3">
          <span class="bg-primary/10 text-primary text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-widest">
            Tracking {{ pendingPredictions.length }} Events
          </span>
          <button
            @click="checkResolutions"
            :disabled="checkingResolutions"
            class="bg-primary-container text-on-primary-container px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider hover:brightness-110 active:scale-[0.98] transition-all disabled:opacity-50"
          >
            {{ checkingResolutions ? 'Checking...' : 'Check Resolutions' }}
          </button>
        </div>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead>
            <tr class="bg-surface-container-low text-on-surface-variant font-label text-[10px] uppercase tracking-[0.08em]">
              <th class="px-6 py-4">Question</th>
              <th class="px-6 py-4 text-right">Predicted %</th>
              <th class="px-6 py-4 text-right">Market %</th>
              <th class="px-6 py-4 text-right">Edge</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant/5">
            <tr v-for="p in pendingPredictions" :key="p.id" class="hover:bg-white/5 transition-colors cursor-pointer" @click="goToReport(p)">
              <td class="px-6 py-4 font-medium text-on-surface">{{ p.question }}</td>
              <td class="px-6 py-4 text-right tabular-nums text-primary">{{ fmtProb(p.predicted) }}</td>
              <td class="px-6 py-4 text-right tabular-nums">{{ fmtProb(p.market) }}</td>
              <td class="px-6 py-4 text-right tabular-nums font-bold" :class="p.edge > 0 ? 'text-secondary' : p.edge < 0 ? 'text-tertiary' : ''">
                {{ fmtEdgePP(p.edge) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Resolved Predictions -->
    <section class="bg-surface-container rounded-xl overflow-hidden">
      <div class="p-6 border-b border-outline-variant/10 flex justify-between items-center flex-wrap gap-3">
        <h3 class="font-headline font-bold text-lg">Resolved Predictions</h3>
        <div class="relative" v-if="resolvedPredictions.length">
          <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">search</span>
          <input v-model="taskSearch" type="text" placeholder="Filter..." class="pl-8 pr-3 py-1.5 bg-surface-container-low border border-outline-variant/20 rounded-lg text-sm text-on-surface placeholder:text-on-surface-variant/50 focus:border-primary-container focus:outline-none w-48" />
        </div>
      </div>
      <div class="overflow-x-auto" v-if="visibleResolved.length">
        <table class="w-full text-left text-sm">
          <thead>
            <tr class="bg-surface-container-low text-on-surface-variant font-label text-[10px] uppercase tracking-[0.08em]">
              <th class="px-6 py-4 cursor-pointer hover:text-primary" @click="toggleSort('date')">
                Date <span v-if="sortField === 'date'" class="text-primary">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-6 py-4">Question</th>
              <th class="px-6 py-4 text-right cursor-pointer hover:text-primary" @click="toggleSort('predicted')">
                Pred <span v-if="sortField === 'predicted'" class="text-primary">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </th>
              <th class="px-6 py-4 text-right">Mkt</th>
              <th class="px-6 py-4 text-right">Edge</th>
              <th class="px-6 py-4 text-center">Result</th>
              <th class="px-6 py-4 text-center">Beat</th>
              <th class="px-6 py-4 text-right cursor-pointer hover:text-primary" @click="toggleSort('model_brier')">
                Brier <span v-if="sortField === 'model_brier'" class="text-primary">{{ sortDir === 'asc' ? '↑' : '↓' }}</span>
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant/5">
            <tr v-for="p in visibleResolved" :key="p.id" class="hover:bg-white/5 transition-colors cursor-pointer" @click="goToReport(p)">
              <td class="px-6 py-4 text-on-surface-variant tabular-nums whitespace-nowrap text-xs">{{ p.dateStr }}</td>
              <td class="px-6 py-4 font-medium text-on-surface">
                {{ p.question }}
              </td>
              <td class="px-6 py-4 text-right tabular-nums">{{ fmtProb(p.predicted) }}</td>
              <td class="px-6 py-4 text-right tabular-nums">{{ p.market != null ? fmtProb(p.market) : '' }}</td>
              <td class="px-6 py-4 text-right tabular-nums font-bold" :class="p.edge > 0 ? 'text-secondary' : p.edge < 0 ? 'text-tertiary' : ''">
                <span v-if="p.edge != null">{{ fmtEdgePP(p.edge) }}</span>
              </td>
              <td class="px-6 py-4 text-center">
                <span
                  class="text-[10px] px-2 py-0.5 rounded font-bold"
                  :class="p.outcome ? 'bg-secondary/10 text-secondary' : 'bg-surface-variant text-on-surface-variant'"
                >
                  {{ p.outcome ? 'YES' : 'NO' }}
                </span>
              </td>
              <td class="px-6 py-4 text-center">
                <span
                  v-if="p.model_brier != null && p.market_brier != null"
                  class="px-3 py-1 rounded-full text-[10px] font-black"
                  :class="p.model_brier < p.market_brier ? 'bg-secondary-container text-on-secondary' : p.model_brier === p.market_brier ? 'bg-surface-variant text-on-surface-variant' : 'bg-error-container text-on-error-container'"
                >
                  {{ p.model_brier < p.market_brier ? 'WIN' : p.model_brier === p.market_brier ? 'TIE' : 'LOSE' }}
                </span>
              </td>
              <td class="px-6 py-4 text-right tabular-nums font-bold" :class="p.model_brier != null && p.model_brier < 0.1 ? 'text-primary' : 'text-on-surface-variant'">
                {{ p.model_brier != null ? p.model_brier.toFixed(4) : '--' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="filteredResolved.length > showLimit" class="p-4 text-center border-t border-outline-variant/10">
        <button @click="showAll = !showAll" class="text-sm font-bold text-primary hover:underline">
          {{ showAll ? 'Show Less' : `Show All (${filteredResolved.length})` }}
        </button>
      </div>
      <p v-if="!resolvedPredictions.length" class="p-12 text-center text-on-surface-variant text-sm">
        No resolved predictions yet. Run some predictions and click "Check Resolutions".
      </p>
    </section>

    <!-- Agent Leaderboard -->
    <section class="bg-surface-container-low rounded-xl p-6 border border-outline-variant/10" v-if="agentReputation.length">
      <h3 class="font-headline font-bold text-lg mb-6 flex items-center gap-2">
        <span class="material-symbols-outlined text-primary">military_tech</span>
        Agent Leaderboard
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="(agent, index) in sortedAgents" :key="agent.name" class="glass-panel p-4 rounded-xl flex flex-col gap-4 relative overflow-hidden">
          <div class="absolute -top-4 -right-4 text-8xl font-black text-white/5 select-none">{{ index + 1 }}</div>
          <div class="flex items-center gap-3">
            <div
              class="w-12 h-12 rounded-full flex items-center justify-center border"
              :class="index === 0 ? 'bg-yellow-400/20 text-yellow-400 border-yellow-400/30' : index === 1 ? 'bg-slate-400/20 text-slate-400 border-slate-400/30' : index === 2 ? 'bg-orange-700/20 text-orange-700 border-orange-700/30' : 'bg-surface-container text-on-surface-variant border-outline-variant/30'"
            >
              <span class="material-symbols-filled">workspace_premium</span>
            </div>
            <div>
              <h4 class="font-bold text-sm">{{ agent.name }}</h4>
              <span class="text-[10px] uppercase font-bold text-on-surface-variant">{{ agent.count }} predictions</span>
            </div>
          </div>
          <div class="space-y-1">
            <div class="flex justify-between text-[10px] uppercase font-bold text-on-surface-variant">
              <span>Accuracy</span>
              <span :class="index === 0 ? 'text-secondary' : 'text-primary'">{{ (agent.accuracy * 100).toFixed(1) }}%</span>
            </div>
            <div class="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
              <div class="h-full rounded-full transition-all duration-500" :class="index === 0 ? 'bg-secondary' : 'bg-primary'" :style="{ width: (agent.accuracy * 100) + '%' }"></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS, CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Legend,
} from 'chart.js'
import api from '../api/client'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

const router = useRouter()

/* ── Raw data refs ── */
const historyTasks = ref([])
const prospectiveAll = ref([])
const prospectiveStats = ref({})
const brierByMethod = ref([])
const agentReputation = ref([])
const error = ref(null)
const checkingResolutions = ref(false)

/* ── Table state ── */
const sortField = ref('date')
const sortDir = ref('desc')
const taskSearch = ref('')
const showAll = ref(false)
const showLimit = 15

/* ══════════════════════════════════════════════
   Unified prediction list
   ══════════════════════════════════════════════ */
const allPredictions = computed(() => {
  const list = []
  for (const p of prospectiveAll.value) {
    const predicted = p.model_probability
    const market = p.market_price_at_prediction != null ? p.market_price_at_prediction * 100 : null
    const isResolved = p.status === 'resolved'
    list.push({
      id: p.id || p.slug,
      taskId: p.task_id || null,
      question: p.question,
      date: p.predicted_at,
      dateStr: fmtDate(p.predicted_at),
      predicted,
      market,
      edge: predicted != null && market != null ? predicted - market : null,
      outcome: isResolved ? p.resolution : null,
      resolved: isResolved,
      model_brier: p.model_brier,
      market_brier: p.market_brier,
      source: 'prospective',
    })
  }
  const prospQuestions = new Set(prospectiveAll.value.map(p => p.question?.toLowerCase()))
  for (const h of historyTasks.value) {
    if (prospQuestions.has(h.question?.toLowerCase())) continue
    const predicted = h.aggregated_probability
    const market = h.market_price != null ? h.market_price * 100 : null
    const isResolved = h.resolved && h.resolution != null
    let model_brier = null
    let market_brier = null
    if (isResolved && predicted != null) {
      const outcome = h.resolution ? 1.0 : 0.0
      model_brier = Math.pow(predicted / 100 - outcome, 2)
      if (h.market_price != null) market_brier = Math.pow(h.market_price - outcome, 2)
    }
    list.push({
      id: h.id, taskId: h.id, question: h.question, date: h.timestamp,
      dateStr: fmtDate(h.timestamp), predicted, market,
      edge: predicted != null && market != null ? predicted - market : null,
      outcome: isResolved ? h.resolution : null, resolved: isResolved,
      model_brier, market_brier, source: 'history',
    })
  }
  return list
})

const pendingPredictions = computed(() => allPredictions.value.filter(p => !p.resolved))
const resolvedPredictions = computed(() => allPredictions.value.filter(p => p.resolved))

/* ── Dashboard stats ── */
const dashModelBrier = computed(() => {
  const scored = resolvedPredictions.value.filter(p => p.model_brier != null)
  if (!scored.length) return null
  return scored.reduce((s, p) => s + p.model_brier, 0) / scored.length
})
const dashMarketBrier = computed(() => {
  const scored = resolvedPredictions.value.filter(p => p.market_brier != null)
  if (!scored.length) return null
  return scored.reduce((s, p) => s + p.market_brier, 0) / scored.length
})
const dashEdge = computed(() => {
  if (dashModelBrier.value == null || dashMarketBrier.value == null) return null
  return dashMarketBrier.value - dashModelBrier.value
})
const winRate = computed(() => {
  const comparable = resolvedPredictions.value.filter(p => p.model_brier != null && p.market_brier != null)
  if (!comparable.length) return null
  const wins = comparable.filter(p => p.model_brier < p.market_brier).length
  return (wins / comparable.length) * 100
})

/* ── Table: filter, sort, paginate ── */
function toggleSort(field) {
  if (sortField.value === field) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else { sortField.value = field; sortDir.value = field === 'date' ? 'desc' : 'asc' }
}
const filteredResolved = computed(() => {
  let list = [...resolvedPredictions.value]
  if (taskSearch.value.trim()) {
    const q = taskSearch.value.trim().toLowerCase()
    list = list.filter(p => (p.question || '').toLowerCase().includes(q))
  }
  list.sort((a, b) => {
    const va = a[sortField.value] ?? -Infinity
    const vb = b[sortField.value] ?? -Infinity
    return sortDir.value === 'asc' ? (va < vb ? -1 : va > vb ? 1 : 0) : (va > vb ? -1 : va < vb ? 1 : 0)
  })
  return list
})
const visibleResolved = computed(() => showAll.value ? filteredResolved.value : filteredResolved.value.slice(0, showLimit))

/* ── Helpers ── */
function fmtProb(val) { return val == null ? '--' : val.toFixed(1) + '%' }
function fmtEdgePP(edge) { return edge == null ? '--' : (edge >= 0 ? '+' : '') + edge.toFixed(1) + 'pp' }
function fmtDate(iso) {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
function goToReport(p) { if (p.taskId) router.push(`/report/${p.taskId}`) }

/* ── Brier by Method (from prospective data) ── */
const allBrierByMethod = computed(() => {
  const resolved = resolvedPredictions.value.filter(p => p.resolved && p.outcome != null)
  if (!resolved.length) return brierByMethod.value // fallback to old calibration API

  // Compute brier per mechanism from prospective all_mechanisms
  const methodScores = {}
  for (const pred of prospectiveAll.value) {
    if (pred.status !== 'resolved' || pred.resolution == null || !pred.all_mechanisms) continue
    const outcome = pred.resolution ? 1.0 : 0.0
    for (const [method, prob] of Object.entries(pred.all_mechanisms)) {
      if (prob == null) continue
      if (!methodScores[method]) methodScores[method] = []
      methodScores[method].push((prob / 100 - outcome) ** 2)
    }
  }

  // Also add market baseline
  const marketScores = []
  for (const pred of prospectiveAll.value) {
    if (pred.status !== 'resolved' || pred.resolution == null || pred.market_price_at_prediction == null) continue
    const outcome = pred.resolution ? 1.0 : 0.0
    marketScores.push((pred.market_price_at_prediction - outcome) ** 2)
  }

  const result = []
  for (const [method, scores] of Object.entries(methodScores)) {
    const avg = scores.reduce((s, v) => s + v, 0) / scores.length
    result.push({
      method: method.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      score: avg,
      isMarket: false,
    })
  }
  if (marketScores.length) {
    const avg = marketScores.reduce((s, v) => s + v, 0) / marketScores.length
    result.push({ method: 'Market Price', score: avg, isMarket: true })
  }

  // If no prospective data, fallback
  if (!result.length) return brierByMethod.value

  // Mark best
  const bestScore = Math.min(...result.filter(m => !m.isMarket).map(m => m.score))
  for (const m of result) {
    m.isBest = !m.isMarket && m.score === bestScore
  }
  return result
})

const sortedAllBrierMethods = computed(() => [...allBrierByMethod.value].sort((a, b) => a.score - b.score))

function brierBarWidth(score) {
  const items = allBrierByMethod.value.length ? allBrierByMethod.value : brierByMethod.value
  const max = items.length ? Math.max(...items.map(m => m.score)) : 0.5
  return Math.min((score / max) * 100, 100) + '%'
}

/* ── Check Resolutions ── */
async function checkResolutions() {
  checkingResolutions.value = true
  try {
    await api.post('/api/history/prospective/check')
    const pResp = await api.get('/api/history/prospective')
    prospectiveAll.value = pResp.data.predictions || []
    prospectiveStats.value = pResp.data.stats || {}
  } catch (err) {
    error.value = 'Failed to check resolutions: ' + err.message
  } finally { checkingResolutions.value = false }
}

/* ── Agent Leaderboard ── */
const sortedAgents = computed(() => [...agentReputation.value].sort((a, b) => b.accuracy - a.accuracy))

/* ── Calibration Chart ── */
const calibrationData = computed(() => {
  const resolved = resolvedPredictions.value.filter(p => p.predicted != null && p.outcome != null)
  if (!resolved.length) return { labels: [], predicted: [], actual: [] }
  const buckets = {}
  for (const t of resolved) {
    const bucket = Math.round(t.predicted / 10) / 10
    const key = bucket.toFixed(1)
    if (!buckets[key]) buckets[key] = { sum: 0, count: 0 }
    buckets[key].sum += t.outcome ? 1 : 0
    buckets[key].count += 1
  }
  const labels = Object.keys(buckets).sort()
  return { labels, predicted: labels.map(l => parseFloat(l)), actual: labels.map(l => buckets[l].sum / buckets[l].count) }
})

const calibrationChartData = computed(() => ({
  labels: calibrationData.value.labels,
  datasets: [
    { label: 'Perfect', data: calibrationData.value.predicted, borderColor: '#424754', borderDash: [6, 4], borderWidth: 2, pointRadius: 0, fill: false },
    { label: 'Model', data: calibrationData.value.actual, borderColor: '#4d8eff', borderWidth: 2.5, pointRadius: 6, pointBackgroundColor: '#4d8eff', pointBorderColor: '#111317', pointBorderWidth: 2, fill: false },
  ],
}))

const calibrationChartOptions = {
  responsive: true,
  maintainAspectRatio: true,
  aspectRatio: 1,
  plugins: {
    legend: { position: 'bottom', labels: { color: '#c2c6d6', padding: 16, usePointStyle: true, font: { size: 11 } } },
  },
  scales: {
    x: {
      title: { display: true, text: 'Predicted Probability', color: '#c2c6d6', font: { weight: '600', size: 11 } },
      min: 0, max: 1,
      grid: { color: 'rgba(66,71,84,0.15)' },
      ticks: { color: '#8c909f', stepSize: 0.2, font: { size: 10 } },
    },
    y: {
      title: { display: true, text: 'Actual Frequency', color: '#c2c6d6', font: { weight: '600', size: 11 } },
      min: 0, max: 1,
      grid: { color: 'rgba(66,71,84,0.15)' },
      ticks: { color: '#8c909f', stepSize: 0.2, font: { size: 10 } },
    },
  },
}

/* ── Data Fetching ── */
async function fetchAll() {
  try {
    const [historyRes, calibrationRes, agentsRes, prospectiveRes] = await Promise.allSettled([
      api.get('/api/history'),
      api.get('/api/history/calibration'),
      api.get('/api/history/agents'),
      api.get('/api/history/prospective'),
    ])
    if (historyRes.status === 'fulfilled') historyTasks.value = (historyRes.value.data.history || []).filter(h => h.has_result)
    if (calibrationRes.status === 'fulfilled') {
      const cal = calibrationRes.value.data.calibration || {}
      brierByMethod.value = Object.entries(cal).map(([method, info]) => ({
        method: method.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        score: info.brier_score,
      }))
    }
    if (agentsRes.status === 'fulfilled') {
      const agents = agentsRes.value.data.agents || []
      agentReputation.value = agents.map(a => ({ name: a.name, avg_brier: a.avg_brier_score, count: a.n_questions, accuracy: a.reputation }))
    }
    if (prospectiveRes.status === 'fulfilled') {
      prospectiveAll.value = prospectiveRes.value.data.predictions || []
      prospectiveStats.value = prospectiveRes.value.data.stats || {}
    }
  } catch (err) { error.value = err.message }
}

onMounted(fetchAll)
</script>
