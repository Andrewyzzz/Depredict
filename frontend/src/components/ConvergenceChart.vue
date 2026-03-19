<template>
  <div class="convergence-chart">
    <h3 class="chart-title">Agent Convergence</h3>
    <Line v-if="hasData" :data="chartData" :options="chartOptions" />
    <p v-else class="no-data">No round data available.</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

const props = defineProps({
  rounds: {
    type: Object,
    default: () => ({}),
    // { round1: [...], round2: [...], round3: [...] }
  },
  marketPrice: {
    type: Number,
    default: null, // 0-1
  },
})

const bullColors = ['#22c55e', '#16a34a', '#15803d']
const bearColors = ['#ef4444', '#dc2626', '#b91c1c']
const neutralColors = ['#6366f1', '#8b5cf6', '#64748b', '#94a3b8']

function getStance(agent) {
  const s = (agent.stance || '').toLowerCase()
  if (s === 'bull' || s === 'bullish' || s === 'yes') return 'bull'
  if (s === 'bear' || s === 'bearish' || s === 'no') return 'bear'
  return 'neutral'
}

const hasData = computed(() => {
  const r = props.rounds
  return (r.round1 && r.round1.length) ||
    (r.round2 && r.round2.length) ||
    (r.round3 && r.round3.length)
})

const chartData = computed(() => {
  const r = props.rounds || {}
  const roundKeys = ['round1', 'round2', 'round3']
  const labels = ['Round 1', 'Round 2', 'Round 3']

  // Collect all unique agent names across rounds
  const agentMap = new Map()
  for (const rk of roundKeys) {
    for (const entry of (r[rk] || [])) {
      const name = entry.agent_name || entry.name
      if (!agentMap.has(name)) {
        agentMap.set(name, { name, stance: getStance(entry) })
      }
    }
  }

  // Color counters
  const colorIdx = { bull: 0, bear: 0, neutral: 0 }
  const colorPools = { bull: bullColors, bear: bearColors, neutral: neutralColors }

  const datasets = []

  for (const [agentName, info] of agentMap) {
    const pool = colorPools[info.stance]
    const color = pool[colorIdx[info.stance] % pool.length]
    colorIdx[info.stance]++

    const data = roundKeys.map((rk) => {
      const entries = r[rk] || []
      const match = entries.find((e) => (e.agent_name || e.name) === agentName)
      return match && match.probability != null ? match.probability : null
    })

    datasets.push({
      label: agentName,
      data,
      borderColor: color,
      backgroundColor: color,
      tension: 0.3,
      pointRadius: 5,
      pointHoverRadius: 7,
      borderWidth: 2,
      spanGaps: true,
    })
  }

  // Market price dashed line
  if (props.marketPrice != null) {
    datasets.push({
      label: 'Market Price',
      data: [props.marketPrice * 100, props.marketPrice * 100, props.marketPrice * 100],
      borderColor: '#94a3b8',
      backgroundColor: 'transparent',
      borderDash: [6, 4],
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 0,
      tension: 0,
    })
  }

  return { labels, datasets }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: true,
  animation: {
    duration: 800,
  },
  scales: {
    y: {
      min: 0,
      max: 100,
      ticks: {
        callback: (v) => v + '%',
        font: { size: 11 },
      },
      grid: {
        color: 'rgba(0,0,0,0.06)',
      },
    },
    x: {
      grid: {
        display: false,
      },
      ticks: {
        font: { size: 12, weight: '600' },
      },
    },
  },
  plugins: {
    legend: {
      position: 'bottom',
      labels: {
        boxWidth: 12,
        boxHeight: 12,
        padding: 16,
        font: { size: 11 },
        usePointStyle: true,
        pointStyle: 'circle',
      },
    },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const val = ctx.parsed.y
          return val != null ? `${ctx.dataset.label}: ${val.toFixed(1)}%` : ''
        },
      },
    },
  },
}))
</script>

<style scoped>
.convergence-chart {
  --_surface-0: var(--surface-0, #ffffff);
  --_border-default: var(--border-default, #e5e7eb);
  --_text-primary: var(--text-primary, #111827);
  --_radius-lg: var(--radius-lg, 12px);
  --_space-6: var(--space-6, 24px);

  background: var(--_surface-0);
  border: 1px solid var(--_border-default);
  border-radius: var(--_radius-lg);
  padding: var(--_space-6);
}

.chart-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--_text-primary);
  margin-bottom: 16px;
}

.no-data {
  font-size: 14px;
  color: var(--text-secondary, #6b7280);
  text-align: center;
  padding: 24px 0;
}
</style>
