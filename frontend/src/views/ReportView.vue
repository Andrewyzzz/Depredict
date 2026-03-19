<template>
  <div class="min-h-[calc(100vh-56px)] bg-[#0b0d11]">
    <!-- Report loaded -->
    <div v-if="report" class="flex min-h-[calc(100vh-56px)]">
      <!-- Internal Report Sidebar -->
      <aside class="w-[200px] shrink-0 bg-[#13151a] border-r border-outline-variant/20 sticky top-[56px] h-[calc(100vh-56px)] flex flex-col overflow-y-auto">
        <div class="p-5">
          <p class="text-[0.625rem] uppercase tracking-[0.15em] text-outline mb-4 px-3 font-label">Report Sections</p>
          <nav class="space-y-0.5">
            <a
              v-for="(section, idx) in sections"
              :key="section.id"
              :href="`#${section.id}`"
              class="flex items-center gap-2.5 px-3 py-2 rounded-xl text-sm transition-all duration-200"
              :class="activeSection === section.id
                ? 'bg-primary-container/10 text-primary font-medium'
                : 'text-on-surface-variant hover:bg-surface-variant/40'"
              @click.prevent="scrollToSection(section.id)"
            >
              <span
                class="material-symbols-outlined text-[18px]"
                :style="activeSection === section.id ? `font-variation-settings: 'FILL' 1` : ''"
              >{{ sectionIcon(idx) }}</span>
              <span class="truncate">{{ section.title }}</span>
            </a>
          </nav>
        </div>
        <div class="mt-auto p-4 space-y-2 border-t border-outline-variant/10">
          <router-link
            to="/analyze"
            class="w-full flex items-center justify-center gap-2 py-2 text-xs font-bold uppercase tracking-widest text-on-surface-variant hover:text-on-surface transition-colors"
          >
            <span class="material-symbols-outlined text-[16px]">arrow_back</span>
            Back to Terminal
          </router-link>
          <button
            @click="exportPdf"
            class="w-full flex items-center justify-center gap-2 py-2.5 bg-primary-container text-on-primary-container rounded-xl font-bold text-xs uppercase tracking-widest hover:brightness-110 transition-all active:scale-95 shadow-[0_0_20px_rgba(77,142,255,0.2)]"
          >
            <span class="material-symbols-outlined text-[18px]">picture_as_pdf</span>
            Export PDF
          </button>
        </div>
      </aside>

      <!-- Main Report Content -->
      <main class="flex-1 p-8 lg:p-12 overflow-y-auto">
        <div class="max-w-4xl mx-auto">
          <!-- Header -->
          <header class="mb-12">
            <div class="flex items-center gap-2 mb-4">
              <span class="px-2 py-1 bg-surface-container-highest text-[0.625rem] font-bold uppercase tracking-widest text-primary border border-primary/20 rounded font-label">Analysis Report</span>
              <span class="text-outline-variant text-xs">&bull;</span>
              <time v-if="report.created_at" class="text-on-surface-variant text-xs font-label tabular-nums">{{ formatDateFull(report.created_at) }}</time>
            </div>
            <h1 class="text-3xl lg:text-4xl font-headline font-bold text-on-surface tracking-tight mb-8 leading-[1.15]">
              {{ report.question }}
            </h1>
            <div class="flex flex-wrap gap-4 items-center">
              <!-- Model Prediction Badge -->
              <div class="flex items-center gap-3 px-4 py-2 bg-surface-container-low rounded-xl border border-outline-variant/20">
                <span class="text-[0.6875rem] uppercase tracking-widest text-on-surface-variant font-label">Model Prediction</span>
                <div class="flex items-center gap-1.5 text-secondary font-headline font-bold">
                  <span class="material-symbols-outlined text-sm" style="font-variation-settings: 'FILL' 1;">{{ predictionIcon }}</span>
                  <span class="tabular-nums">{{ (report.final_probability * 100).toFixed(1) }}%</span>
                </div>
              </div>
              <!-- Market Price Badge -->
              <div v-if="report.market_price != null" class="flex items-center gap-3 px-4 py-2 bg-surface-container-low rounded-xl border border-outline-variant/20">
                <span class="text-[0.6875rem] uppercase tracking-widest text-on-surface-variant font-label">Market Price</span>
                <div class="text-on-surface font-headline font-bold tabular-nums">
                  {{ (report.market_price * 100).toFixed(1) }}%
                  <span v-if="edge != null" class="text-xs ml-1" :class="edge >= 0 ? 'text-secondary' : 'text-tertiary'">
                    {{ edge >= 0 ? '+' : '' }}{{ edge.toFixed(1) }}% edge
                  </span>
                </div>
              </div>
              <!-- Confidence Bars -->
              <div class="flex items-center gap-3 px-4 py-2 bg-surface-container-low rounded-xl border border-outline-variant/20">
                <span class="text-[0.6875rem] uppercase tracking-widest text-on-surface-variant font-label">Confidence</span>
                <div class="flex gap-1">
                  <div
                    v-for="i in 5"
                    :key="i"
                    class="w-1 h-3 rounded-full"
                    :class="i <= confidenceLevel ? 'bg-primary' : 'bg-outline-variant'"
                  ></div>
                </div>
              </div>
            </div>
          </header>

          <!-- Rendered Markdown -->
          <article class="markdown-body text-on-surface-variant leading-relaxed font-body" v-html="renderedMarkdown"></article>

          <!-- Footer -->
          <footer class="mt-16 pt-8 border-t border-outline-variant/20 flex flex-col md:flex-row justify-between items-start gap-4">
            <div>
              <p class="text-[0.6875rem] uppercase tracking-widest text-outline font-label">Report ID</p>
              <p class="text-xs font-mono text-on-surface-variant tabular-nums">{{ route.params.taskId }}</p>
            </div>
            <div class="md:text-right">
              <p class="text-[0.6875rem] uppercase tracking-widest text-outline font-label">Generated by</p>
              <p class="text-xs font-bold text-primary font-headline">DePredict Engine</p>
            </div>
          </footer>
        </div>
      </main>
    </div>

    <!-- Loading State -->
    <div v-else-if="loading" class="flex items-center justify-center min-h-[calc(100vh-56px)]">
      <div class="text-center">
        <span class="material-symbols-outlined text-primary text-4xl animate-spin mb-4 block">progress_activity</span>
        <p class="text-on-surface-variant text-sm font-label uppercase tracking-widest">Loading report...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex items-center justify-center min-h-[calc(100vh-56px)] p-8">
      <div class="max-w-md w-full px-6 py-5 bg-error-container/20 border border-error/20 rounded-xl text-error text-sm">
        <div class="flex items-center gap-2 mb-2">
          <span class="material-symbols-outlined text-lg">error</span>
          <span class="font-bold uppercase tracking-widest text-xs font-label">Error</span>
        </div>
        {{ error }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { marked } from 'marked'
import api from '../api/client'

const route = useRoute()
const report = ref(null)
const loading = ref(true)
const error = ref(null)
const activeSection = ref('')

const renderedMarkdown = computed(() => {
  if (!report.value?.markdown) return ''
  return marked(report.value.markdown)
})

const sections = computed(() => {
  if (!report.value?.markdown) return []
  const headings = []
  const regex = /^#{1,3}\s+(.+)$/gm
  let match
  while ((match = regex.exec(report.value.markdown)) !== null) {
    const title = match[1].trim()
    const id = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
    headings.push({ id, title })
  }
  return headings
})

const predictionIcon = computed(() => {
  if (!report.value) return 'analytics'
  return report.value.final_probability >= 0.5 ? 'trending_up' : 'trending_down'
})

const edge = computed(() => {
  if (!report.value || report.value.market_price == null) return null
  return (report.value.final_probability - report.value.market_price) * 100
})

const confidenceLevel = computed(() => {
  if (!report.value) return 0
  const p = report.value.final_probability
  // Map probability distance from 50% to confidence bars (1-5)
  const strength = Math.abs(p - 0.5) * 2 // 0 to 1
  return Math.max(1, Math.min(5, Math.ceil(strength * 5)))
})

const sectionIcons = ['analytics', 'query_stats', 'hub', 'verified_user', 'history', 'schema', 'source', 'assessment', 'neurology', 'insights']

function sectionIcon(idx) {
  return sectionIcons[idx % sectionIcons.length]
}

function scrollToSection(id) {
  activeSection.value = id
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDateFull(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).toUpperCase() + ' ' + d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZoneName: 'short',
  })
}

function exportPdf() {
  alert('PDF export is a planned feature. For now, use your browser\'s Print > Save as PDF.')
}

async function fetchReport() {
  loading.value = true
  error.value = null
  const taskId = route.params.taskId
  try {
    // First try loading from history results (for past analyses)
    const historyRes = await api.get(`/api/history/${taskId}/result`)
    const data = historyRes.data
    // Build a report-like object from the debate result
    report.value = {
      question: data.question,
      created_at: data.timestamp,
      final_probability: (data.aggregation_mechanisms?.hybrid?.probability ?? data.aggregated_probability ?? 0) / 100,
      market_price: data.market_price,
      markdown: buildMarkdownFromResult(data),
    }
  } catch {
    // Fallback: try the report generation API (for in-session tasks)
    try {
      const response = await api.get(`/api/report/${taskId}`)
      report.value = response.data
    } catch (err) {
      error.value = err.response?.data?.error || 'Failed to load report'
    }
  } finally {
    loading.value = false
  }
}

function buildMarkdownFromResult(data) {
  const lines = []
  lines.push(`# ${data.question}\n`)

  // Summary
  const hybrid = data.aggregation_mechanisms?.hybrid?.probability
  if (hybrid != null) {
    lines.push(`## Summary`)
    lines.push(`**Model Prediction:** ${hybrid.toFixed(1)}%`)
    if (data.market_price != null) {
      lines.push(`**Market Price:** ${(data.market_price * 100).toFixed(1)}%`)
      const edge = (hybrid / 100 - data.market_price) * 100
      lines.push(`**Edge:** ${edge > 0 ? '+' : ''}${edge.toFixed(1)}%`)
    }
    lines.push('')
  }

  // Aggregation methods
  const mechs = data.aggregation_mechanisms
  if (mechs) {
    lines.push(`## Aggregation Methods`)
    lines.push('| Method | Probability |')
    lines.push('|--------|------------|')
    for (const [method, info] of Object.entries(mechs)) {
      const p = info.probability
      lines.push(`| ${method.replace(/_/g, ' ')} | ${p != null ? p.toFixed(1) + '%' : 'N/A'} |`)
    }
    lines.push('')
  }

  // Agent results (Round 3)
  const round3 = data.rounds?.round3
  if (round3 && round3.length) {
    lines.push(`## Agent Final Predictions (Round 3)`)
    for (const agent of round3) {
      const prob = agent.probability != null ? `${agent.probability.toFixed(1)}%` : 'N/A'
      lines.push(`### ${agent.agent_name} (${agent.stance || 'neutral'}) — ${prob}`)
      if (agent.reasoning) {
        lines.push(agent.reasoning)
      }
      lines.push('')
    }
  }

  // Sources
  const sources = data.rag_sources
  if (sources && sources.length) {
    lines.push(`## Sources`)
    for (const s of sources) {
      lines.push(`- [${s.title}](${s.url})`)
    }
    lines.push('')
  }

  // Entity graph
  const eg = data.entity_graph
  if (eg && eg.entities && eg.entities.length) {
    lines.push(`## Knowledge Graph`)
    lines.push(`**Entities:** ${eg.entities.length} | **Relations:** ${eg.relations?.length || 0} | **Timeline:** ${eg.timeline?.length || 0}`)
    lines.push('')
    for (const e of eg.entities) {
      lines.push(`- **${e.name}** (${e.type})${e.description ? ': ' + e.description : ''}`)
    }
    lines.push('')
  }

  return lines.join('\n')
}

onMounted(fetchReport)
</script>

<style scoped>
/* Markdown content dark theme styles */
.markdown-body :deep(h1) {
  font-size: 1.75rem;
  margin: 2rem 0 1rem;
  color: var(--color-on-surface);
  font-family: var(--font-headline);
  font-weight: 700;
  letter-spacing: -0.01em;
}

.markdown-body :deep(h2) {
  border-left: 4px solid var(--color-primary-container);
  padding-left: 1rem;
  margin-top: 2.5rem;
  margin-bottom: 1rem;
  font-family: var(--font-headline);
  font-weight: 700;
  font-size: 1.5rem;
  color: var(--color-on-surface);
}

.markdown-body :deep(h3) {
  font-size: 1.125rem;
  margin: 1.5rem 0 0.75rem;
  color: var(--color-on-surface);
  font-family: var(--font-headline);
  font-weight: 600;
}

.markdown-body :deep(p) {
  margin-bottom: 1rem;
  line-height: 1.75;
}

.markdown-body :deep(strong) {
  color: var(--color-on-surface);
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: var(--color-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: opacity 0.15s;
}

.markdown-body :deep(a:hover) {
  opacity: 0.8;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin-bottom: 1rem;
  padding-left: 1.5rem;
}

.markdown-body :deep(li) {
  margin-bottom: 0.375rem;
  line-height: 1.7;
}

.markdown-body :deep(blockquote) {
  border-left: 4px solid var(--color-primary-container);
  padding: 1rem 1.5rem;
  font-style: italic;
  color: var(--color-on-surface-variant);
  margin: 1.5rem 0;
  background: rgba(77, 142, 255, 0.05);
  border-radius: 0 0.75rem 0.75rem 0;
}

.markdown-body :deep(code) {
  background: var(--color-surface-container-lowest);
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.875em;
  color: var(--color-primary);
}

.markdown-body :deep(pre) {
  background: var(--color-surface-container-lowest);
  padding: 1.5rem;
  border-radius: 0.75rem;
  overflow-x: auto;
  margin: 1.5rem 0;
  border: 1px solid rgba(66, 71, 84, 0.2);
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: var(--color-on-surface);
  font-size: 0.8125rem;
  line-height: 1.6;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
  font-family: var(--font-body);
  font-size: 0.875rem;
}

.markdown-body :deep(th) {
  background: var(--color-surface-container);
  text-align: left;
  padding: 0.75rem 1rem;
  color: var(--color-primary);
  font-family: var(--font-headline);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.6875rem;
  font-weight: 700;
  border-bottom: 1px solid rgba(66, 71, 84, 0.3);
}

.markdown-body :deep(td) {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid rgba(66, 71, 84, 0.2);
  color: var(--color-on-surface);
}

.markdown-body :deep(tr:hover td) {
  background: rgba(255, 255, 255, 0.02);
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(66, 71, 84, 0.3);
  margin: 2rem 0;
}
</style>
