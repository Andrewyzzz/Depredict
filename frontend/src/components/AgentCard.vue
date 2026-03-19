<template>
  <div class="agent-card" :class="stanceClass" @click="expanded = !expanded">
    <div class="agent-header">
      <div class="agent-avatar" :class="stanceClass">
        {{ initials }}
      </div>
      <div class="agent-info">
        <span class="agent-name">{{ agent.agent_name || agent.name }}</span>
        <span class="stance-badge" :class="stanceClass">{{ stanceLabel }}</span>
      </div>
    </div>
    <div class="agent-probability">
      {{ agent.probability != null ? agent.probability.toFixed(1) : 'N/A' }}<span class="pct">%</span>
    </div>
    <!-- Mini probability bar -->
    <div class="prob-bar-track">
      <div
        class="prob-bar-fill"
        :class="stanceClass"
        :style="{ width: (agent.probability || 0) + '%' }"
      ></div>
    </div>
    <p class="agent-reasoning" :class="{ 'reasoning-expanded': expanded }" :title="agent.reasoning">
      {{ expanded ? agent.reasoning : truncatedReasoning }}
    </p>
    <span v-if="(agent.reasoning || '').length > 180" class="expand-hint">
      {{ expanded ? 'Show less' : 'Read more' }}
    </span>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  agent: {
    type: Object,
    required: true,
    // { name, stance, probability, reasoning }
  },
})

const expanded = ref(false)

const initials = computed(() => {
  const name = props.agent.agent_name || props.agent.name || '?'
  return name.slice(0, 2)
})

const stanceClass = computed(() => {
  const s = (props.agent.stance || '').toLowerCase()
  if (s === 'bull' || s === 'bullish' || s === 'yes') return 'bull'
  if (s === 'bear' || s === 'bearish' || s === 'no') return 'bear'
  return 'neutral'
})

const stanceLabel = computed(() => {
  const s = (props.agent.stance || '').toLowerCase()
  if (s === 'bull' || s === 'bullish' || s === 'yes') return 'Bull'
  if (s === 'bear' || s === 'bearish' || s === 'no') return 'Bear'
  return 'Neutral'
})

const truncatedReasoning = computed(() => {
  const text = props.agent.reasoning || ''
  return text.length > 180 ? text.slice(0, 177) + '...' : text
})
</script>

<style scoped>
.agent-card {
  background: var(--surface-0, #fff);
  border: 1px solid var(--border-default, var(--gray-200, #e5e7eb));
  border-radius: var(--radius-lg, 12px);
  padding: 18px;
  transition: box-shadow var(--transition-fast, 0.15s), transform var(--transition-fast, 0.15s);
  cursor: pointer;
  animation: cardFadeIn 0.3s ease forwards;
  border-left: 4px solid transparent;
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.agent-card:hover {
  box-shadow: var(--shadow-md, 0 4px 16px rgba(0, 0, 0, 0.08));
  transform: translateY(-2px);
}

.agent-card.bull {
  border-left-color: var(--color-success, #22c55e);
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.03) 0%, transparent 40%);
}

.agent-card.bear {
  border-left-color: var(--color-danger, #ef4444);
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.03) 0%, transparent 40%);
}

.agent-card.neutral {
  border-left-color: var(--gray-300, #d1d5db);
}

.agent-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.agent-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.agent-avatar.bull {
  background: var(--color-success, #22c55e);
}

.agent-avatar.bear {
  background: var(--color-danger, #ef4444);
}

.agent-avatar.neutral {
  background: var(--gray-300, #9ca3af);
}

.agent-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, var(--gray-900, #111827));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stance-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  width: fit-content;
}

.stance-badge.bull {
  background: #dcfce7;
  color: #166534;
}

.stance-badge.bear {
  background: #fef2f2;
  color: #991b1b;
}

.stance-badge.neutral {
  background: var(--surface-2, var(--gray-100, #f3f4f6));
  color: var(--text-tertiary, var(--gray-500, #6b7280));
}

.agent-probability {
  font-size: 36px;
  font-weight: 800;
  color: var(--text-primary, var(--gray-900, #111827));
  margin-bottom: 6px;
  font-variant-numeric: tabular-nums;
}

.pct {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-tertiary, var(--gray-500, #6b7280));
}

/* Mini probability bar */
.prob-bar-track {
  height: 6px;
  background: var(--surface-2, var(--gray-100, #f3f4f6));
  border-radius: 3px;
  margin-bottom: 12px;
  overflow: hidden;
}

.prob-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.prob-bar-fill.bull {
  background: linear-gradient(90deg, #22c55e, #4ade80);
}

.prob-bar-fill.bear {
  background: linear-gradient(90deg, #ef4444, #f87171);
}

.prob-bar-fill.neutral {
  background: linear-gradient(90deg, #9ca3af, #d1d5db);
}

.agent-reasoning {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-tertiary, var(--gray-500, #6b7280));
  margin: 0;
  transition: max-height 0.3s ease;
}

.reasoning-expanded {
  /* Allow full text display */
}

.expand-hint {
  display: inline-block;
  margin-top: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-primary, var(--primary, #6366f1));
  cursor: pointer;
}

.expand-hint:hover {
  text-decoration: underline;
}
</style>
