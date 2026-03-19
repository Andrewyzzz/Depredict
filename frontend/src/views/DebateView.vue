<template>
  <div class="max-w-5xl mx-auto px-6 py-12 font-body">

    <!-- Header -->
    <section class="max-w-3xl mx-auto text-center space-y-2 mb-12">
      <h1 class="text-4xl font-headline font-bold text-on-surface tracking-tight">Intelligence Engine</h1>
      <p class="text-on-surface-variant font-label text-sm uppercase tracking-[0.1em]">Synthesize Real-Time Market Sentiment</p>
    </section>

    <!-- Input Form (visible when not running and not complete) -->
    <section v-if="!store.isRunning && !store.isComplete" class="max-w-3xl mx-auto space-y-6 mb-16">
      <form @submit.prevent="handleSubmit" class="space-y-5">
        <!-- Question Input -->
        <div class="relative group">
          <input
            v-model="question"
            type="text"
            class="w-full bg-surface-container-lowest border-b border-outline-variant/40 py-4 px-2 text-xl font-headline text-on-surface focus:outline-none focus:border-primary transition-all placeholder:text-on-surface-variant/30"
            placeholder="Enter your question (e.g. Will ETH break $3k this week?)"
            required
          />
          <div class="absolute bottom-0 left-0 w-0 h-[2px] bg-primary group-focus-within:w-full transition-all duration-500"></div>
        </div>

        <!-- Quick-pick chips -->
        <div class="flex flex-wrap gap-2">
          <button
            v-for="ex in exampleQuestions"
            :key="ex"
            type="button"
            class="px-4 py-1.5 rounded-full glass-panel text-xs text-on-surface-variant hover:text-primary hover:border-primary/40 transition-all cursor-pointer"
            @click="question = ex"
          >{{ ex }}</button>
        </div>

        <!-- Market Price + Submit Row -->
        <div class="flex flex-col md:flex-row gap-4">
          <div class="flex-1 relative">
            <span class="absolute left-2 top-1/2 -translate-y-1/2 text-on-surface-variant/40 font-headline text-xs uppercase tracking-widest">Entry</span>
            <input
              v-model.number="marketPrice"
              type="number"
              step="0.01"
              min="0"
              max="1"
              class="w-full bg-surface-container-lowest border-b border-outline-variant/40 py-3 pl-16 pr-2 font-headline tabular-nums text-on-surface focus:outline-none focus:border-primary transition-all"
              placeholder="0.65"
            />
          </div>
          <button
            type="submit"
            :disabled="store.isLoading"
            class="bg-primary-container text-on-primary-container px-8 py-3 rounded-xl font-bold font-headline uppercase tracking-[0.08em] hover:scale-[1.02] active:scale-95 transition-all shadow-[0_0_20px_rgba(77,142,255,0.3)] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            <span class="material-symbols-outlined text-sm">bolt</span>
            {{ store.isLoading ? 'Analyzing...' : 'Run Analysis' }}
          </button>
        </div>
      </form>
    </section>

    <!-- Error Section -->
    <section v-if="store.error" class="max-w-2xl mx-auto mb-8">
      <div class="flex items-center gap-3 px-5 py-4 rounded-xl bg-error-container/20 border border-error/20 text-error text-sm">
        <span class="material-symbols-outlined text-lg">error</span>
        <span>{{ store.error }}</span>
      </div>
    </section>

    <!-- Progress Bar (during debate) -->
    <section v-if="store.isRunning" class="max-w-2xl mx-auto mb-16">
      <div class="flex items-center justify-between mb-3 px-1">
        <span class="text-[0.6875rem] uppercase tracking-[0.12em] text-primary font-bold">
          {{ store.progress.message || store.progress.stage || 'Initializing...' }}
        </span>
        <span class="text-[0.6875rem] font-bold font-headline tabular-nums text-on-surface">{{ store.progress.percent }}%</span>
      </div>
      <div class="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-primary-container to-primary shadow-[0_0_20px_rgba(77,142,255,0.3)] transition-all duration-700"
          :style="{ width: store.progress.percent + '%' }"
        ></div>
      </div>
    </section>

    <!-- Aggregated Probability Display (when complete) -->
    <section v-if="store.isComplete && modelProbability != null" class="text-center mb-20">
      <div class="inline-block relative">
        <div class="absolute -inset-8 bg-primary/5 blur-3xl rounded-full"></div>
        <span class="text-[0.6875rem] uppercase tracking-[0.2em] text-on-surface-variant block mb-2">Aggregated Probability</span>
        <div class="text-8xl md:text-9xl font-headline font-bold text-primary tracking-tighter tabular-nums drop-shadow-[0_0_30px_rgba(173,198,255,0.2)]">
          {{ modelProbability.toFixed(1) }}%
        </div>
        <div class="flex items-center justify-center gap-2 mt-4 font-headline font-medium" :class="convictionColor">
          <span class="material-symbols-outlined">{{ convictionIcon }}</span>
          <span>{{ convictionLabel }}</span>
        </div>
      </div>

      <!-- Market Context -->
      <div v-if="store.currentMarketPrice != null" class="mt-8 flex items-center justify-center gap-6 flex-wrap">
        <div class="glass-panel px-5 py-3 rounded-xl text-center">
          <span class="micro-label block mb-1">Market Price</span>
          <span class="text-xl font-headline font-bold tabular-nums text-on-surface">{{ (store.currentMarketPrice * 100).toFixed(1) }}%</span>
        </div>
        <div class="glass-panel px-5 py-3 rounded-xl text-center">
          <span class="micro-label block mb-1">Edge</span>
          <span
            class="text-xl font-headline font-bold tabular-nums"
            :class="edge > 0 ? 'text-secondary' : edge < 0 ? 'text-tertiary' : 'text-on-surface-variant'"
          >{{ edgeFormatted || '--' }}</span>
        </div>
        <div v-if="formattedEndDate" class="glass-panel px-5 py-3 rounded-xl text-center">
          <span class="micro-label block mb-1">Resolves</span>
          <span class="text-sm font-headline font-bold text-on-surface">{{ formattedEndDate }}</span>
        </div>
      </div>
    </section>

    <!-- Streaming Agent Cards (during debate or after completion) -->
    <section v-if="(store.isRunning || store.isComplete) && (bullAgents.length || bearAgents.length)">
      <div class="grid md:grid-cols-2 gap-8">

        <!-- Bulls Side -->
        <div class="space-y-6">
          <div class="flex items-center gap-3 px-2">
            <div class="h-2 w-2 rounded-full bg-secondary shadow-[0_0_8px_rgba(74,225,118,0.5)]"></div>
            <h3 class="text-[0.6875rem] uppercase tracking-[0.15em] font-bold text-secondary">The Bulls{{ bullAgents.length ? ` (${bullAgents.length})` : '' }}</h3>
          </div>
          <div
            v-for="agent in bullAgents"
            :key="agent.name"
            class="glass-card p-6 rounded-xl border-l-4 border-l-secondary/40"
          >
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="h-10 w-10 rounded-xl bg-secondary/10 flex items-center justify-center text-secondary border border-secondary/20">
                  <span class="material-symbols-outlined">psychology</span>
                </div>
                <div>
                  <h4 class="font-headline font-bold text-on-surface text-sm">{{ agent.name }}</h4>
                  <p class="text-[0.625rem] text-on-surface-variant uppercase tracking-tighter">{{ agent.specialty || agent.stage || 'Agent' }}</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="px-2 py-0.5 bg-secondary/10 text-secondary border border-secondary/20 rounded text-[0.65rem] font-black uppercase tracking-widest">Bull</span>
                <span v-if="agent.probability != null" class="text-secondary font-headline font-bold tabular-nums text-lg">{{ agent.probability.toFixed(1) }}%</span>
              </div>
            </div>
            <p v-if="agent.reasoning" class="text-sm text-on-surface-variant leading-relaxed">{{ cleanReasoning(agent.reasoning) }}</p>
          </div>
        </div>

        <!-- Bears Side -->
        <div class="space-y-6">
          <div class="flex items-center gap-3 px-2">
            <div class="h-2 w-2 rounded-full bg-tertiary shadow-[0_0_8px_rgba(255,179,173,0.5)]"></div>
            <h3 class="text-[0.6875rem] uppercase tracking-[0.15em] font-bold text-tertiary">The Bears{{ bearAgents.length ? ` (${bearAgents.length})` : '' }}</h3>
          </div>
          <div
            v-for="agent in bearAgents"
            :key="agent.name"
            class="glass-card p-6 rounded-xl border-l-4 border-l-tertiary/40"
          >
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-3">
                <div class="h-10 w-10 rounded-xl bg-tertiary/10 flex items-center justify-center text-tertiary border border-tertiary/20">
                  <span class="material-symbols-outlined">warning</span>
                </div>
                <div>
                  <h4 class="font-headline font-bold text-on-surface text-sm">{{ agent.name }}</h4>
                  <p class="text-[0.625rem] text-on-surface-variant uppercase tracking-tighter">{{ agent.specialty || agent.stage || 'Agent' }}</p>
                </div>
              </div>
              <div class="flex items-center gap-3">
                <span class="px-2 py-0.5 bg-tertiary/10 text-tertiary border border-tertiary/20 rounded text-[0.65rem] font-black uppercase tracking-widest">Bear</span>
                <span v-if="agent.probability != null" class="text-tertiary font-headline font-bold tabular-nums text-lg">{{ agent.probability.toFixed(1) }}%</span>
              </div>
            </div>
            <p v-if="agent.reasoning" class="text-sm text-on-surface-variant leading-relaxed">{{ cleanReasoning(agent.reasoning) }}</p>
          </div>
        </div>

      </div>
    </section>

    <!-- Loading placeholder cards during debate when no agents yet -->
    <section v-if="store.isRunning && !bullAgents.length && !bearAgents.length" class="max-w-2xl mx-auto">
      <div class="grid md:grid-cols-2 gap-6">
        <div class="glass-panel p-6 rounded-xl border border-dashed border-outline-variant/30 flex flex-col items-center justify-center text-center space-y-3 min-h-[160px]">
          <div class="w-8 h-8 rounded-full border-2 border-primary/20 border-t-primary animate-spin"></div>
          <p class="text-[0.65rem] uppercase tracking-widest font-bold text-on-surface-variant">Awaiting Bull Agents...</p>
        </div>
        <div class="glass-panel p-6 rounded-xl border border-dashed border-outline-variant/30 flex flex-col items-center justify-center text-center space-y-3 min-h-[160px]">
          <div class="w-8 h-8 rounded-full border-2 border-tertiary/20 border-t-tertiary animate-spin"></div>
          <p class="text-[0.65rem] uppercase tracking-widest font-bold text-on-surface-variant">Awaiting Bear Agents...</p>
        </div>
      </div>
    </section>

    <!-- Debate Rounds Accordion (after completion) -->
    <section v-if="fullResult?.rounds" class="mt-16 max-w-4xl mx-auto">
      <h3 class="text-[0.6875rem] uppercase tracking-[0.15em] font-bold text-primary mb-6 px-2">Debate Rounds</h3>
      <div class="space-y-3">
        <div
          v-for="(roundKey, idx) in ['round1', 'round2', 'round3']"
          :key="idx"
          class="glass-card rounded-xl overflow-hidden"
        >
          <div
            class="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-white/5 transition-all"
            @click="toggleRound(idx)"
          >
            <span class="font-headline font-bold text-on-surface text-sm">Round {{ idx + 1 }}</span>
            <div class="flex items-center gap-4">
              <span class="text-xs text-on-surface-variant tabular-nums">{{ (fullResult.rounds?.[roundKey] || []).length }} agents</span>
              <span
                class="material-symbols-outlined text-on-surface-variant transition-transform duration-200"
                :class="{ 'rotate-180': expandedRounds.has(idx) }"
              >expand_more</span>
            </div>
          </div>
          <div v-if="expandedRounds.has(idx)" class="px-6 pb-5 space-y-3">
            <div
              v-for="(entry, eidx) in (fullResult.rounds?.[roundKey] || [])"
              :key="eidx"
              class="p-4 rounded-lg bg-surface-container-low/50"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="font-headline font-bold text-on-surface text-sm">{{ entry.agent_name }}</span>
                <span class="font-headline font-bold tabular-nums text-primary">
                  {{ entry.probability != null ? entry.probability.toFixed(1) + '%' : 'N/A' }}
                </span>
              </div>
              <p class="text-sm text-on-surface-variant leading-relaxed">{{ cleanReasoning(entry.reasoning) }}</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Footer actions (after completion) -->
    <footer v-if="store.isComplete" class="mt-20 pt-12 border-t border-outline-variant/10 max-w-4xl mx-auto">
      <div class="flex flex-col md:flex-row items-center justify-between gap-6">
        <div class="flex items-center gap-6">
          <div class="text-center md:text-left">
            <span class="text-[0.625rem] text-on-surface-variant uppercase tracking-widest block mb-1">Agents</span>
            <span class="font-headline text-sm tabular-nums text-on-surface">{{ latestAgentResults.length }} completed</span>
          </div>
          <div v-if="edgeFormatted" class="text-center md:text-left">
            <span class="text-[0.625rem] text-on-surface-variant uppercase tracking-widest block mb-1">Edge vs Market</span>
            <span
              class="font-headline text-sm tabular-nums font-bold"
              :class="edge > 0 ? 'text-secondary' : 'text-tertiary'"
            >{{ edgeFormatted }}</span>
          </div>
        </div>
        <div class="flex gap-4">
          <button
            class="px-5 py-2 glass-card rounded-lg text-xs font-bold uppercase tracking-widest text-on-surface hover:border-primary/40 transition-all"
            @click="resetToInput"
          >New Analysis</button>
          <router-link
            v-if="store.taskId"
            :to="`/report/${store.taskId}`"
            class="px-5 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg text-xs font-bold uppercase tracking-widest hover:bg-primary/20 transition-all"
          >View Full Report</router-link>
        </div>
      </div>
    </footer>

  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useDebateStore } from '../store/index'

const store = useDebateStore()
const question = ref('')
const marketPrice = ref(null)
const expandedRounds = reactive(new Set())

// If navigated from Scanner with a question already running, populate inputs
onMounted(() => {
  if (store.currentQuestion) {
    question.value = store.currentQuestion
  }
  if (store.currentMarketPrice != null) {
    marketPrice.value = store.currentMarketPrice
  }
})

const exampleQuestions = [
  'Will Bitcoin exceed $100k by 2026?',
  'Will AI pass the Turing test by 2027?',
  'Will SpaceX land on Mars by 2030?',
]

const fullResult = computed(() => store.fullResult)

// Deduplicate agent results - keep latest per agent
const latestAgentResults = computed(() => {
  const seen = new Map()
  for (const a of store.agentResults) {
    const key = a.agent_name || a.name
    seen.set(key, a)
  }
  return Array.from(seen.values())
})

// Split agents into bull / bear based on probability or stance
const bullAgents = computed(() => {
  // First try fullResult agents with stance
  if (fullResult.value?.agents && Array.isArray(fullResult.value.agents)) {
    return fullResult.value.agents
      .filter(a => a.stance === 'bull' || a.stance === 'BULL')
      .map(a => ({
        name: a.name,
        specialty: a.specialty || '',
        stance: 'bull',
        probability: a.final?.probability ?? null,
        reasoning: a.final?.reasoning || '',
        stage: '',
      }))
  }
  // Fallback to streaming agent results
  return latestAgentResults.value.filter(a => {
    if (a.stance === 'bull' || a.stance === 'BULL') return true
    if (a.probability != null && a.probability >= 50) return true
    return false
  }).map(a => ({
    name: a.agent_name || a.name,
    specialty: a.specialty || '',
    stance: 'bull',
    probability: a.probability ?? null,
    reasoning: a.reasoning || '',
    stage: a.stage || '',
  }))
})

const bearAgents = computed(() => {
  // First try fullResult agents with stance
  if (fullResult.value?.agents && Array.isArray(fullResult.value.agents)) {
    return fullResult.value.agents
      .filter(a => a.stance === 'bear' || a.stance === 'BEAR')
      .map(a => ({
        name: a.name,
        specialty: a.specialty || '',
        stance: 'bear',
        probability: a.final?.probability ?? null,
        reasoning: a.final?.reasoning || '',
        stage: '',
      }))
  }
  // Fallback to streaming agent results
  return latestAgentResults.value.filter(a => {
    if (a.stance === 'bear' || a.stance === 'BEAR') return true
    if (a.probability != null && a.probability < 50) return true
    return false
  }).map(a => ({
    name: a.agent_name || a.name,
    specialty: a.specialty || '',
    stance: 'bear',
    probability: a.probability ?? null,
    reasoning: a.reasoning || '',
    stage: a.stage || '',
  }))
})

// Agents with stance info for BullBearSplit (from fullResult.agents)
const bullBearAgents = computed(() => {
  const agents = fullResult.value?.agents
  if (!agents || !Array.isArray(agents)) return []
  return agents.map((a) => ({
    agent_name: a.name,
    stance: a.stance,
    probability: a.final?.probability ?? null,
    reasoning: a.final?.reasoning || '',
  }))
})

// Model probability from hybrid mechanism (0-100 scale)
const modelProbability = computed(() => {
  const mechanisms = fullResult.value?.aggregation_mechanisms
  if (!mechanisms) return null
  const hybrid = mechanisms.hybrid?.probability
  if (hybrid != null) return hybrid
  // Fallback to simple average
  return fullResult.value?.aggregated_probability ?? null
})

const edge = computed(() => {
  if (!marketPrice.value || modelProbability.value == null) return null
  return (modelProbability.value / 100) - marketPrice.value
})

const edgeFormatted = computed(() => {
  if (edge.value == null) return ''
  const pct = (edge.value * 100).toFixed(1)
  return edge.value > 0 ? `+${pct}%` : `${pct}%`
})

const edgeClass = computed(() => {
  if (edge.value == null) return ''
  return edge.value > 0 ? 'positive' : 'negative'
})

// Conviction display helpers
const convictionLabel = computed(() => {
  if (modelProbability.value == null) return ''
  if (modelProbability.value >= 75) return 'High Conviction Signal'
  if (modelProbability.value >= 55) return 'Moderate Conviction'
  if (modelProbability.value >= 45) return 'Low Conviction / Uncertain'
  if (modelProbability.value >= 25) return 'Moderate Bearish Signal'
  return 'High Bearish Conviction'
})

const convictionIcon = computed(() => {
  if (modelProbability.value == null) return 'remove'
  if (modelProbability.value >= 55) return 'trending_up'
  if (modelProbability.value >= 45) return 'trending_flat'
  return 'trending_down'
})

const convictionColor = computed(() => {
  if (modelProbability.value == null) return 'text-on-surface-variant'
  if (modelProbability.value >= 55) return 'text-secondary'
  if (modelProbability.value >= 45) return 'text-on-surface-variant'
  return 'text-tertiary'
})

const formattedEndDate = computed(() => {
  const d = store.currentEndDate
  if (!d) return ''
  try {
    const date = new Date(d)
    if (isNaN(date.getTime())) return ''
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
  } catch { return '' }
})

function cleanReasoning(text) {
  if (!text) return ''
  return text
    // Remove entire quoted blocks that contain raw table data (pipes)
    .replace(/##begin_quote##\s*[\s\S]*?\s*##end_quote##/g, (match) => {
      const inner = match.replace(/##begin_quote##\s*/, '').replace(/\s*##end_quote##/, '').trim()
      // If it looks like raw table data (multiple pipes), remove entirely
      if ((inner.match(/\|/g) || []).length >= 3) return ''
      // Otherwise keep the content without markers
      return inner
    })
    // Remove document references like [文档 1], [Document 2, 6], [文档1]
    .replace(/\s*\[(?:文档|Document)\s*\d+(?:\s*[,，]\s*\d+)*\s*\]/g, '')
    // Clean up leftover double spaces / leading punctuation
    .replace(/  +/g, ' ')
    .replace(/。\s*。/g, '。')
    .trim()
}

function toggleRound(idx) {
  if (expandedRounds.has(idx)) {
    expandedRounds.delete(idx)
  } else {
    expandedRounds.add(idx)
  }
}

function resetToInput() {
  store.cleanup()
  store.fullResult = null
  store.agentResults = []
  store.progress = { stage: '', percent: 0, message: '' }
  store.error = null
  store.taskId = null
}

async function handleSubmit() {
  if (!question.value.trim()) return
  try {
    await store.startDebate(question.value.trim(), marketPrice.value || null)
  } catch {
    // error already in store
  }
}

onUnmounted(() => {
  store.cleanup()
})
</script>
