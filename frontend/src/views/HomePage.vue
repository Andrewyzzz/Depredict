<template>
  <div class="home-page">
    <!-- Home-specific Top Nav (overlays the App nav) -->
    <nav class="fixed top-0 w-full z-50 bg-[#111317]/80 backdrop-blur-xl border-b border-white/10 shadow-[0_0_20px_rgba(59,130,246,0.08)]">
      <div class="flex justify-between items-center px-8 h-20 w-full max-w-[1440px] mx-auto">
        <div class="text-2xl font-bold tracking-tighter text-on-surface font-headline">DePredict</div>
        <div class="hidden md:flex items-center gap-8">
          <router-link to="/history" class="micro-label text-on-surface-variant hover:text-on-surface transition-colors font-headline">Performance</router-link>
          <router-link to="/scan" class="micro-label text-on-surface-variant hover:text-on-surface transition-colors font-headline">Markets</router-link>
          <router-link to="/history" class="micro-label text-on-surface-variant hover:text-on-surface transition-colors font-headline">Predictions</router-link>
        </div>
        <div class="flex items-center gap-4">
          <router-link to="/analyze" class="bg-primary-container text-on-primary-container px-6 py-2 rounded-xl font-bold text-sm hover:shadow-[0_0_20px_rgba(77,142,255,0.4)] transition-all active:scale-95">
            Launch Terminal
          </router-link>
        </div>
      </div>
    </nav>

    <main class="pt-20">
      <!-- Hero Section -->
      <section class="relative min-h-[780px] flex flex-col items-center justify-center px-6 overflow-hidden">
        <div class="absolute inset-0 z-0 bg-[radial-gradient(circle_at_50%_50%,_rgba(77,142,255,0.1),_transparent_70%)]"></div>
        <div class="max-w-4xl w-full text-center z-10 space-y-8">
          <h1 class="font-headline font-bold text-5xl md:text-7xl leading-[1.1] tracking-tight">
            Predict Smarter Than <br/>
            <span class="text-primary italic">the Market</span>
          </h1>
          <p class="text-on-surface-variant text-lg md:text-xl max-w-2xl mx-auto leading-relaxed">
            Harness high-frequency AI multi-agent debates and 9 proprietary aggregation methods to identify market inefficiencies with institutional precision.
          </p>
          <div class="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <router-link to="/analyze" class="bg-primary-container text-on-primary-container px-8 py-4 rounded-xl font-bold text-md w-full sm:w-auto hover:shadow-[0_0_30px_rgba(77,142,255,0.5)] transition-all text-center">
              Start Analysis
            </router-link>
            <router-link to="/history" class="border border-outline-variant text-on-surface px-8 py-4 rounded-xl font-bold text-md w-full sm:w-auto hover:bg-white/5 transition-all text-center">
              View Track Record
            </router-link>
          </div>
          <!-- HUD Stats -->
          <div class="pt-16 grid grid-cols-2 gap-8 max-w-lg mx-auto">
            <div class="flex flex-col items-center">
              <span class="font-headline text-[0.6875rem] uppercase tracking-[0.15em] text-on-surface-variant mb-2">Model Edge</span>
              <div class="tabular-nums font-headline text-4xl font-bold tracking-tighter" :class="modelEdge > 0 ? 'text-secondary glow-secondary' : modelEdge < 0 ? 'text-tertiary' : 'text-on-surface-variant'">
                {{ modelEdge != null ? (modelEdge >= 0 ? '+' : '') + modelEdge.toFixed(4) : '--' }}
              </div>
            </div>
            <div class="flex flex-col items-center">
              <span class="font-headline text-[0.6875rem] uppercase tracking-[0.15em] text-on-surface-variant mb-2">Win Rate</span>
              <div class="tabular-nums text-primary font-headline text-4xl font-bold tracking-tighter">
                {{ winRate != null ? winRate.toFixed(1) + '%' : '--' }}
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Real-time Stats Section -->
      <section class="py-24 px-8 max-w-[1440px] mx-auto">
        <div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <div v-for="stat in statCards" :key="stat.label" class="glass-panel p-6 rounded-xl group hover:border-white/20 transition-all">
            <div class="text-on-surface-variant text-[0.6875rem] font-headline uppercase tracking-widest mb-4">{{ stat.label }}</div>
            <div class="tabular-nums text-2xl font-bold" :class="stat.colorClass">{{ stat.display }}</div>
          </div>
        </div>
      </section>

      <!-- System Architecture / How It Works -->
      <section class="py-24 bg-surface-container-low">
        <div class="max-w-[1440px] mx-auto px-8">
          <div class="mb-16">
            <h2 class="font-headline text-3xl font-bold tracking-tight">System Architecture</h2>
            <p class="text-on-surface-variant mt-2">End-to-end quantitative prediction pipeline.</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-12">
            <div class="space-y-6">
              <div class="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center text-primary">
                <span class="material-symbols-outlined">filter_alt</span>
              </div>
              <h3 class="text-xl font-headline font-bold">01. Market Selection</h3>
              <p class="text-on-surface-variant leading-relaxed">Our scanners monitor thousands of prediction markets across Polymarket, Kalshi, and Manifold to find high-liquidity opportunities with potential pricing gaps.</p>
            </div>
            <div class="space-y-6">
              <div class="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center text-primary">
                <span class="material-symbols-outlined">diversity_3</span>
              </div>
              <h3 class="text-xl font-headline font-bold">02. AI Debate</h3>
              <p class="text-on-surface-variant leading-relaxed">Multiple LLM-based agents take adversarial positions, critiquing each other's logical fallacies and evidence quality to refine the final probability output.</p>
            </div>
            <div class="space-y-6">
              <div class="w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center text-primary">
                <span class="material-symbols-outlined">layers</span>
              </div>
              <h3 class="text-xl font-headline font-bold">03. Aggregation</h3>
              <p class="text-on-surface-variant leading-relaxed">Final probabilities are computed using 9 diverse methods, including weighted median, trimmed mean, and Bayesian updating to eliminate outlier bias.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Active Intel / Recent Predictions -->
      <section class="py-24 px-8 max-w-[1440px] mx-auto">
        <div class="flex justify-between items-end mb-10">
          <div>
            <h2 class="font-headline text-3xl font-bold tracking-tight">Active Intel</h2>
            <p class="text-on-surface-variant mt-2">Real-time model vs market comparisons.</p>
          </div>
          <router-link to="/history" class="text-primary font-headline text-[0.6875rem] uppercase tracking-widest hover:underline flex items-center gap-2">
            View All <span class="material-symbols-outlined text-sm">arrow_forward</span>
          </router-link>
        </div>
        <div class="overflow-x-auto glass-panel rounded-xl">
          <table class="w-full text-left" v-if="recentPredictions.length">
            <thead>
              <tr class="bg-white/5 font-headline text-[0.6875rem] uppercase tracking-[0.1em] text-on-surface-variant border-b border-white/5">
                <th class="px-8 py-6">Question</th>
                <th class="px-8 py-6">Model Prob.</th>
                <th class="px-8 py-6">Market Price</th>
                <th class="px-8 py-6">Edge</th>
                <th class="px-8 py-6">Status</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-white/5">
              <tr
                v-for="p in recentPredictions"
                :key="p.id"
                class="hover:bg-white/5 transition-colors group cursor-pointer"
                @click="goToReport(p)"
              >
                <td class="px-8 py-6 font-medium text-on-surface truncate max-w-xs">{{ truncate(p.question, 55) }}</td>
                <td class="px-8 py-6 tabular-nums font-bold text-primary">{{ fmtPct(p.model_probability) }}</td>
                <td class="px-8 py-6 tabular-nums">{{ p.market_price_at_prediction != null ? (p.market_price_at_prediction * 100).toFixed(1) + '%' : '--' }}</td>
                <td class="px-8 py-6 tabular-nums" :class="edgeColor(p)">{{ fmtEdge(p) }}</td>
                <td class="px-8 py-6">
                  <span v-if="p.status === 'pending'" class="bg-surface-container-highest text-on-surface-variant px-3 py-1 rounded-full text-[10px] uppercase font-bold tracking-tighter">Pending</span>
                  <span v-else-if="p.model_brier != null && p.market_brier != null && p.model_brier < p.market_brier" class="bg-secondary/10 text-secondary px-3 py-1 rounded-full text-[10px] uppercase font-bold tracking-tighter">Resolved Win</span>
                  <span v-else-if="p.status === 'resolved'" class="bg-tertiary/10 text-tertiary px-3 py-1 rounded-full text-[10px] uppercase font-bold tracking-tighter">Resolved</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="p-12 text-center text-on-surface-variant text-sm">
            Loading predictions...
          </div>
        </div>
      </section>

      <!-- The Quant Advantage -->
      <section class="py-24 bg-surface-container-lowest">
        <div class="max-w-[1440px] mx-auto px-8">
          <div class="text-center mb-20">
            <h2 class="font-headline text-4xl font-bold tracking-tight">The Quant Advantage</h2>
            <p class="text-on-surface-variant mt-4 text-lg">Engineered for accuracy, built for scalability.</p>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div class="bg-surface-container-low p-10 rounded-xl border border-white/5 hover:border-primary/20 transition-all">
              <div class="mb-6 text-primary">
                <span class="material-symbols-outlined text-4xl">smart_toy</span>
              </div>
              <h4 class="text-xl font-headline font-bold mb-4">Adversarial Debate</h4>
              <p class="text-on-surface-variant text-sm leading-relaxed">Unlike simple LLM prompting, our agents act as specialized debaters, uncovering hidden edge cases and probabilistic nuances the market overlooks.</p>
            </div>
            <div class="bg-surface-container-low p-10 rounded-xl border border-white/5 hover:border-primary/20 transition-all">
              <div class="mb-6 text-primary">
                <span class="material-symbols-outlined text-4xl">functions</span>
              </div>
              <h4 class="text-xl font-headline font-bold mb-4">Multiple Aggregation</h4>
              <p class="text-on-surface-variant text-sm leading-relaxed">We don't trust a single number. We use diverse statistical ensembles to find the "wisdom of the agents," significantly outperforming individual model calls.</p>
            </div>
            <div class="bg-surface-container-low p-10 rounded-xl border border-white/5 hover:border-primary/20 transition-all">
              <div class="mb-6 text-primary">
                <span class="material-symbols-outlined text-4xl">timeline</span>
              </div>
              <h4 class="text-xl font-headline font-bold mb-4">Prospective Tracking</h4>
              <p class="text-on-surface-variant text-sm leading-relaxed">Continuous calibration against real-world outcomes ensures our Brier scores remain tight and our model edge is statistically significant.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Bottom CTA -->
      <section class="py-32 px-8">
        <div class="max-w-4xl mx-auto glass-panel p-16 rounded-[2rem] text-center relative overflow-hidden">
          <div class="absolute inset-0 bg-primary/5 -z-10 blur-3xl rounded-full translate-y-12"></div>
          <h2 class="font-headline text-4xl md:text-5xl font-bold tracking-tight mb-8">Ready to out-calculate the market?</h2>
          <router-link to="/scan" class="inline-flex items-center gap-3 bg-primary-container text-on-primary-container px-10 py-5 rounded-xl font-bold text-lg hover:shadow-[0_0_40px_rgba(77,142,255,0.4)] transition-all">
            Find Mispriced Markets
            <span class="material-symbols-outlined">search</span>
          </router-link>
        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="bg-surface-container-lowest border-t border-white/5 mt-auto">
      <div class="flex flex-col md:flex-row justify-between items-center p-12 w-full max-w-[1440px] mx-auto">
        <div class="mb-8 md:mb-0 space-y-2">
          <div class="text-lg font-black text-on-surface font-headline">DePredict</div>
          <p class="text-xs text-on-surface-variant">© 2024 DePredict. High-Performance Quantitative Infrastructure.</p>
        </div>
        <div class="flex flex-wrap justify-center gap-8">
          <a class="text-xs text-on-surface-variant hover:text-on-surface transition-colors" href="#">Terms</a>
          <a class="text-xs text-on-surface-variant hover:text-on-surface transition-colors" href="#">Privacy</a>
          <a class="text-xs text-on-surface-variant hover:text-on-surface transition-colors" href="#">API Docs</a>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const predictions = ref([])
const stats = ref({})

// Computed
const modelEdge = computed(() => {
  if (stats.value.avg_model_brier != null && stats.value.avg_market_brier != null) {
    return stats.value.avg_market_brier - stats.value.avg_model_brier
  }
  return null
})

const winRate = computed(() => {
  const resolved = predictions.value.filter(p => p.status === 'resolved' && p.model_brier != null && p.market_brier != null)
  if (!resolved.length) return null
  const wins = resolved.filter(p => p.model_brier < p.market_brier).length
  return (wins / resolved.length) * 100
})

const statCards = computed(() => [
  { label: 'Total Predictions', display: stats.value.total ?? '--', colorClass: '' },
  { label: 'Resolved', display: stats.value.resolved ?? '--', colorClass: '' },
  { label: 'Pending', display: stats.value.pending ?? '--', colorClass: '' },
  { label: 'Model Brier', display: stats.value.avg_model_brier != null ? stats.value.avg_model_brier.toFixed(4) : '--', colorClass: 'text-secondary' },
  { label: 'Market Brier', display: stats.value.avg_market_brier != null ? stats.value.avg_market_brier.toFixed(4) : '--', colorClass: '' },
  { label: 'Model Edge', display: modelEdge.value != null ? (modelEdge.value >= 0 ? '+' : '') + (modelEdge.value * 100).toFixed(1) + '%' : '--', colorClass: modelEdge.value > 0 ? 'text-secondary' : modelEdge.value < 0 ? 'text-tertiary' : '' },
])

const recentPredictions = computed(() => {
  return [...predictions.value]
    .sort((a, b) => new Date(b.predicted_at) - new Date(a.predicted_at))
    .slice(0, 5)
})

// Helpers
function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.substring(0, len) + '...' : str
}

function fmtPct(val) {
  if (val == null) return '--'
  return val.toFixed(1) + '%'
}

function fmtEdge(p) {
  if (p.model_probability == null || p.market_price_at_prediction == null) return '--'
  const edge = p.model_probability - p.market_price_at_prediction * 100
  return (edge >= 0 ? '+' : '') + edge.toFixed(1) + '%'
}

function edgeColor(p) {
  if (p.model_probability == null || p.market_price_at_prediction == null) return ''
  const edge = p.model_probability - p.market_price_at_prediction * 100
  return edge > 0 ? 'text-secondary' : edge < 0 ? 'text-tertiary' : ''
}

function goToReport(p) {
  if (p.task_id) router.push(`/report/${p.task_id}`)
}

// Data fetching
onMounted(async () => {
  try {
    const resp = await api.get('/api/history/prospective')
    predictions.value = resp.data.predictions || []
    stats.value = resp.data.stats || {}
  } catch (e) {
    // Graceful fallback
  }
})
</script>

<style scoped>
.home-page {
  /* Homepage hides the App.vue nav since it has its own */
}
</style>
