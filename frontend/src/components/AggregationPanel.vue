<template>
  <div class="aggregation-panel">
    <h2>Aggregation Results</h2>

    <div class="table-container">
      <table class="agg-table">
        <thead>
          <tr>
            <th>Method</th>
            <th class="num">Probability</th>
            <th>Distribution</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(entry, method) in mechanisms"
            :key="method"
            :class="{ highlight: method === hybridMethod }"
          >
            <td class="method-name">
              {{ formatMethodName(method) }}
              <span v-if="method === hybridMethod" class="hybrid-badge">Hybrid</span>
            </td>
            <td class="num prob-cell">
              {{ entry.probability != null ? entry.probability.toFixed(1) + '%' : 'N/A' }}
            </td>
            <td>
              <div class="prob-bar-track">
                <div
                  class="prob-bar-fill"
                  :class="barClass((entry.probability || 0) / 100)"
                  :style="{ '--target-width': (entry.probability || 0) + '%' }"
                ></div>
                <div
                  v-if="marketPrice != null"
                  class="market-marker"
                  :style="{ left: (marketPrice * 100) + '%' }"
                  title="Market price"
                ></div>
              </div>
            </td>
            <td class="details-cell">
              {{ entry.details || '--' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="comparison" v-if="marketPrice != null && hybridProb != null">
      <div class="comparison-item">
        <span class="comp-label">Model (Hybrid)</span>
        <span class="comp-value primary">{{ hybridProb.toFixed(1) }}%</span>
      </div>
      <div class="comparison-vs">vs</div>
      <div class="comparison-item">
        <span class="comp-label">Market</span>
        <span class="comp-value">{{ (marketPrice * 100).toFixed(1) }}%</span>
      </div>
      <div class="comparison-divider"></div>
      <div class="comparison-item">
        <span class="comp-label">Edge</span>
        <span
          class="comp-value edge-big"
          :class="edgeValue > 0 ? 'positive' : 'negative'"
        >
          {{ edgeValue > 0 ? '+' : '' }}{{ edgeValue.toFixed(1) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  mechanisms: {
    type: Object,
    required: true,
    // { method_name: { probability, details }, ... }
  },
  marketPrice: {
    type: Number,
    default: null,
  },
})

const methodNames = {
  simple_average: 'Simple Average',
  weighted_average: 'Confidence-Weighted Average',
  median: 'Median',
  trimmed_mean: 'Trimmed Mean',
  bayesian_update: 'Bayesian Update',
  extremized_mean: 'Extremized Mean',
  geometric_mean_odds: 'Geometric Mean of Odds',
  harmonic_mean_odds: 'Harmonic Mean of Odds',
  hybrid: 'Hybrid Ensemble',
}

function formatMethodName(key) {
  return methodNames[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const hybridMethod = computed(() => {
  if (props.mechanisms.hybrid) return 'hybrid'
  const entries = Object.entries(props.mechanisms)
  if (!entries.length) return null
  const mean = entries.reduce((s, [, v]) => s + v.probability, 0) / entries.length
  let closest = entries[0][0]
  let minDist = Math.abs(entries[0][1].probability - mean)
  for (const [key, val] of entries) {
    const dist = Math.abs(val.probability - mean)
    if (dist < minDist) {
      minDist = dist
      closest = key
    }
  }
  return closest
})

const hybridProb = computed(() => {
  if (!hybridMethod.value || !props.mechanisms[hybridMethod.value]) return null
  return props.mechanisms[hybridMethod.value].probability
})

const edgeValue = computed(() => {
  if (hybridProb.value == null || props.marketPrice == null) return 0
  return hybridProb.value - (props.marketPrice * 100)
})

function barClass(prob) {
  if (prob >= 0.7) return 'high'
  if (prob >= 0.4) return 'mid'
  return 'low'
}
</script>

<style scoped>
.aggregation-panel {
  background: var(--surface-0, #fff);
  border-radius: var(--radius-lg, 12px);
  border: 1px solid var(--border-default, var(--gray-200, #e5e7eb));
  padding: 24px;
  box-shadow: var(--shadow-md, 0 2px 8px rgba(0,0,0,0.04));
}

.aggregation-panel h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary, var(--gray-900, #111827));
  margin: 0 0 16px;
}

.table-container {
  overflow-x: auto;
}

.agg-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.agg-table th {
  text-align: left;
  padding: 10px 14px;
  background: var(--surface-1, var(--gray-50, #f9fafb));
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary, var(--gray-500, #6b7280));
  border-bottom: 1px solid var(--border-default, var(--gray-200, #e5e7eb));
}

.agg-table th.num {
  text-align: right;
}

.agg-table td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-default, var(--gray-100, #f3f4f6));
  color: var(--text-secondary, var(--gray-700, #374151));
  transition: background var(--transition-fast, 0.15s);
}

.agg-table tr:last-child td {
  border-bottom: none;
}

.agg-table tr:hover td {
  background: var(--surface-1, var(--gray-50, #f9fafb));
}

/* Highlight row for hybrid/best method */
.agg-table tr.highlight {
  background: rgba(99, 102, 241, 0.04);
}

.agg-table tr.highlight td {
  border-bottom-color: rgba(99, 102, 241, 0.1);
}

.agg-table tr.highlight:hover td {
  background: rgba(99, 102, 241, 0.07);
}

.method-name {
  font-weight: 600;
  color: var(--text-primary, var(--gray-900, #111827));
  white-space: nowrap;
}

.hybrid-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 8px;
  background: var(--brand-primary, var(--primary, #6366f1));
  color: white;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  vertical-align: middle;
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.3);
}

.prob-cell {
  text-align: right;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* ── Animated Bars ── */
.prob-bar-track {
  position: relative;
  height: 10px;
  background: var(--surface-2, var(--gray-100, #f3f4f6));
  border-radius: 5px;
  min-width: 140px;
  overflow: visible;
}

.prob-bar-fill {
  height: 100%;
  border-radius: 5px;
  width: 0;
  animation: barGrow 0.6s ease forwards;
}

@keyframes barGrow {
  from { width: 0; }
  to { width: var(--target-width); }
}

.prob-bar-fill.high {
  background: linear-gradient(90deg, #22c55e, #4ade80);
}

.prob-bar-fill.mid {
  background: linear-gradient(90deg, var(--brand-primary, #6366f1), #818cf8);
}

.prob-bar-fill.low {
  background: linear-gradient(90deg, #ef4444, #f87171);
}

.market-marker {
  position: absolute;
  top: -4px;
  width: 2px;
  height: 18px;
  background: var(--text-primary, var(--gray-900, #111827));
  border-radius: 1px;
  transform: translateX(-1px);
}

.market-marker::after {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-primary, var(--gray-900, #111827));
}

.details-cell {
  font-size: 12px;
  color: var(--text-tertiary, var(--gray-500, #6b7280));
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Comparison Section ── */
.comparison {
  display: flex;
  align-items: center;
  gap: 28px;
  margin-top: 24px;
  padding: 20px 24px;
  border-top: 1px solid var(--border-default, var(--gray-200, #e5e7eb));
  justify-content: center;
  background: var(--surface-1, var(--gray-50, #f9fafb));
  border-radius: 0 0 var(--radius-lg, 12px) var(--radius-lg, 12px);
  margin-left: -24px;
  margin-right: -24px;
  margin-bottom: -24px;
  padding-bottom: 24px;
}

.comparison-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.comp-label {
  font-size: 12px;
  color: var(--text-tertiary, var(--gray-500, #6b7280));
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.comp-value {
  font-size: 28px;
  font-weight: 800;
  color: var(--text-primary, var(--gray-900, #111827));
  font-variant-numeric: tabular-nums;
}

.comp-value.primary {
  color: var(--brand-primary, var(--primary, #6366f1));
}

.comp-value.positive {
  color: var(--color-success, var(--success, #22c55e));
}

.comp-value.negative {
  color: var(--color-danger, var(--danger, #ef4444));
}

.edge-big {
  font-size: 32px;
}

.comparison-vs {
  font-size: 14px;
  color: var(--text-tertiary, var(--gray-300, #d1d5db));
  font-weight: 700;
}

.comparison-divider {
  width: 1px;
  height: 40px;
  background: var(--border-default, var(--gray-200, #e5e7eb));
}
</style>
