<template>
  <div class="probability-gauge">
    <svg viewBox="0 0 200 120" class="gauge-svg">
      <!-- Background arc -->
      <path
        :d="arcPath"
        fill="none"
        :stroke="bgColor"
        stroke-width="14"
        stroke-linecap="round"
      />
      <!-- Filled arc -->
      <path
        :d="arcPath"
        fill="none"
        :stroke="fillColor"
        stroke-width="14"
        stroke-linecap="round"
        :stroke-dasharray="arcLength"
        :stroke-dashoffset="dashOffset"
        class="gauge-fill"
      />
      <!-- Market price diamond marker -->
      <g v-if="marketPrice != null">
        <polygon
          :points="marketDiamondPoints"
          :fill="'var(--_text-primary)'"
          class="market-marker"
        />
      </g>
      <!-- Probability text -->
      <text x="100" y="88" text-anchor="middle" class="gauge-value">
        {{ probability.toFixed(1) }}%
      </text>
      <!-- Label -->
      <text x="100" y="108" text-anchor="middle" class="gauge-label">
        {{ label }}
      </text>
    </svg>
    <!-- Edge below if market price provided -->
    <div v-if="marketPrice != null && edgeValue != null" class="edge-info">
      <span class="edge-label">Edge vs Market</span>
      <span class="edge-value" :class="edgeValue > 0 ? 'positive' : 'negative'">
        {{ edgeValue > 0 ? '+' : '' }}{{ edgeValue.toFixed(1) }}%
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'

const props = defineProps({
  probability: { type: Number, default: 50 },
  marketPrice: { type: Number, default: null }, // 0-1
  label: { type: String, default: 'Model Prediction' },
})

const animated = ref(false)

onMounted(() => {
  // Trigger animation after mount
  requestAnimationFrame(() => {
    animated.value = true
  })
})

// Arc geometry: semicircle from left to right
const cx = 100
const cy = 95
const r = 75

const arcPath = computed(() => {
  // Semicircle from 180 degrees to 0 degrees (left to right)
  return `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`
})

const arcLength = computed(() => {
  return Math.PI * r // Half circumference
})

const dashOffset = computed(() => {
  if (!animated.value) return arcLength.value
  const fill = (props.probability / 100) * arcLength.value
  return arcLength.value - fill
})

const bgColor = 'var(--_border-default)'

const fillColor = computed(() => {
  if (props.probability < 30) return '#ef4444'
  if (props.probability > 70) return '#22c55e'
  return '#6366f1'
})

// Market price diamond marker position on arc
const marketDiamondPoints = computed(() => {
  if (props.marketPrice == null) return ''
  const angle = Math.PI - (props.marketPrice * Math.PI) // 180 to 0 degrees
  const mx = cx + r * Math.cos(angle)
  const my = cy - r * Math.sin(angle)
  const s = 5
  return `${mx},${my - s} ${mx + s},${my} ${mx},${my + s} ${mx - s},${my}`
})

const edgeValue = computed(() => {
  if (props.marketPrice == null) return null
  return props.probability - (props.marketPrice * 100)
})
</script>

<style scoped>
.probability-gauge {
  --_brand-primary: var(--brand-primary, #6366f1);
  --_surface-0: var(--surface-0, #ffffff);
  --_border-default: var(--border-default, #e5e7eb);
  --_text-primary: var(--text-primary, #111827);
  --_text-secondary: var(--text-secondary, #6b7280);
  --_radius-lg: var(--radius-lg, 12px);
  --_shadow-md: var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1));

  display: flex;
  flex-direction: column;
  align-items: center;
}

.gauge-svg {
  width: 240px;
  max-width: 100%;
  height: auto;
}

.gauge-fill {
  transition: stroke-dashoffset 1s ease;
}

.gauge-value {
  font-size: 28px;
  font-weight: 800;
  fill: var(--_text-primary);
  font-family: inherit;
}

.gauge-label {
  font-size: 11px;
  font-weight: 500;
  fill: var(--_text-secondary);
  font-family: inherit;
}

.market-marker {
  opacity: 0.85;
}

.edge-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  margin-top: 4px;
}

.edge-label {
  font-size: 12px;
  color: var(--_text-secondary);
  font-weight: 500;
}

.edge-value {
  font-size: 20px;
  font-weight: 700;
}

.edge-value.positive {
  color: #22c55e;
}

.edge-value.negative {
  color: #ef4444;
}
</style>
