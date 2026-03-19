<template>
  <div class="analysis-progress">
    <div class="pipeline">
      <div
        v-for="(node, idx) in stages"
        :key="node.id"
        class="pipeline-stage"
      >
        <!-- Connector line (before each node except first) -->
        <div
          v-if="idx > 0"
          class="connector"
          :class="{ filled: stageIndex(node.id) <= currentStageIndex }"
        ></div>

        <!-- Node circle -->
        <div
          class="node"
          :class="{
            completed: stageIndex(node.id) < currentStageIndex,
            active: stageIndex(node.id) === currentStageIndex && !isCompleted,
            future: stageIndex(node.id) > currentStageIndex,
            'all-done': isCompleted,
          }"
        >
          <!-- Checkmark for completed -->
          <svg
            v-if="stageIndex(node.id) < currentStageIndex || isCompleted"
            class="check-icon"
            width="16"
            height="16"
            viewBox="0 0 16 16"
            fill="none"
          >
            <path
              d="M3 8.5L6.5 12L13 4"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          <!-- Step number for active/future -->
          <span v-else class="node-number">{{ idx + 1 }}</span>
        </div>

        <!-- Label -->
        <span
          class="node-label"
          :class="{
            'label-active': stageIndex(node.id) === currentStageIndex && !isCompleted,
            'label-completed': stageIndex(node.id) < currentStageIndex || isCompleted,
          }"
        >{{ node.label }}</span>
      </div>
    </div>

    <!-- Agent avatars for active stage -->
    <div v-if="activeAgents.length" class="agent-avatars">
      <div
        v-for="(agent, i) in activeAgents"
        :key="agent.agent_name || agent.name || i"
        class="agent-avatar"
        :class="getStanceClass(agent)"
        :style="{ animationDelay: (i * 0.1) + 's' }"
        :title="agent.agent_name || agent.name"
      >
        {{ getInitials(agent) }}
      </div>
    </div>

    <!-- Progress message -->
    <p v-if="message" class="progress-message">{{ message }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: { type: String, default: '' },
  percent: { type: Number, default: 0 },
  message: { type: String, default: '' },
  agentResults: { type: Array, default: () => [] },
})

const stages = [
  { id: 'retrieve', label: 'Retrieve' },
  { id: 'round1', label: 'Round 1' },
  { id: 'round2', label: 'Round 2' },
  { id: 'round3', label: 'Round 3' },
  { id: 'aggregate', label: 'Aggregate' },
]

const stageMapping = {
  initializing: 'retrieve',
  created: 'retrieve',
  retrieving: 'retrieve',
  extracting_entities: 'retrieve',
  debating_r1: 'round1',
  debating_r2: 'round2',
  debating_r3: 'round3',
  meta_predicting: 'aggregate',
  aggregating: 'aggregate',
  generating_report: 'aggregate',
  completed: 'completed',
  failed: 'failed',
}

const isCompleted = computed(() => props.stage === 'completed')

function stageIndex(id) {
  return stages.findIndex((s) => s.id === id)
}

const currentStageIndex = computed(() => {
  const mapped = stageMapping[props.stage]
  if (!mapped || mapped === 'failed') return -1
  if (mapped === 'completed') return stages.length
  return stageIndex(mapped)
})

const activeAgents = computed(() => {
  if (!props.agentResults || !props.agentResults.length) return []
  // Show agents relevant to current stage
  const seen = new Map()
  for (const a of props.agentResults) {
    const key = a.agent_name || a.name
    seen.set(key, a)
  }
  return Array.from(seen.values()).slice(-8)
})

function getStanceClass(agent) {
  const s = (agent.stance || '').toLowerCase()
  if (s === 'bull' || s === 'bullish' || s === 'yes') return 'avatar-bull'
  if (s === 'bear' || s === 'bearish' || s === 'no') return 'avatar-bear'
  return 'avatar-neutral'
}

function getInitials(agent) {
  const name = agent.agent_name || agent.name || '?'
  return name.slice(0, 2)
}
</script>

<style scoped>
.analysis-progress {
  --_brand-primary: var(--brand-primary, #6366f1);
  --_surface-0: var(--surface-0, #ffffff);
  --_surface-1: var(--surface-1, #f9fafb);
  --_border-default: var(--border-default, #e5e7eb);
  --_text-primary: var(--text-primary, #111827);
  --_text-secondary: var(--text-secondary, #6b7280);
  --_text-tertiary: var(--text-tertiary, #9ca3af);
  --_radius-lg: var(--radius-lg, 12px);
  --_shadow-md: var(--shadow-md, 0 4px 6px -1px rgba(0,0,0,0.1));
  --_space-4: var(--space-4, 16px);
  --_space-6: var(--space-6, 24px);
  --_transition-fast: var(--transition-fast, 0.15s ease);

  background: var(--_surface-0);
  border: 1px solid var(--_border-default);
  border-radius: var(--_radius-lg);
  padding: var(--_space-6);
}

.pipeline {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 0;
  position: relative;
}

.pipeline-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  min-width: 0;
}

.connector {
  position: absolute;
  top: 18px;
  right: calc(50% + 20px);
  left: calc(-50% + 20px);
  height: 3px;
  background: var(--_border-default);
  border-radius: 2px;
  transition: background 0.4s ease;
  z-index: 0;
}

.connector.filled {
  background: var(--_brand-primary);
}

.node {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  position: relative;
  z-index: 1;
  transition: all 0.3s ease;
}

.node.completed,
.node.all-done {
  background: var(--_brand-primary);
  color: white;
  border: 2px solid var(--_brand-primary);
}

.node.active {
  background: white;
  color: var(--_brand-primary);
  border: 2px solid var(--_brand-primary);
  animation: pulse 2s ease-in-out infinite;
}

.node.future {
  background: var(--_surface-1);
  color: var(--_text-tertiary);
  border: 2px solid var(--_border-default);
}

.check-icon {
  color: currentColor;
}

.node-number {
  font-variant-numeric: tabular-nums;
}

.node-label {
  margin-top: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--_text-tertiary);
  white-space: nowrap;
  transition: color var(--_transition-fast);
}

.label-active {
  color: var(--_brand-primary);
}

.label-completed {
  color: var(--_text-secondary);
}

.agent-avatars {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-top: var(--_space-4);
  flex-wrap: wrap;
}

.agent-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: white;
  animation: slideInUp 0.3s ease both;
}

.avatar-bull {
  background: #22c55e;
}

.avatar-bear {
  background: #ef4444;
}

.avatar-neutral {
  background: #9ca3af;
}

.progress-message {
  text-align: center;
  margin-top: 12px;
  font-size: 13px;
  color: var(--_text-secondary);
}

@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(99, 102, 241, 0);
  }
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
