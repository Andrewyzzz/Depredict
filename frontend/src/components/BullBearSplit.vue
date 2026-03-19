<template>
  <div class="bull-bear-split">
    <h3 class="section-title">Bull vs Bear</h3>

    <div class="split-grid">
      <!-- Bull column -->
      <div class="column bull-column">
        <div class="column-header bull-header">
          <span class="column-icon">&#9650;</span>
          <span>Bull ({{ bullAgents.length }})</span>
        </div>
        <div class="agent-list">
          <div
            v-for="agent in bullAgents"
            :key="agent.agent_name || agent.name"
            class="agent-item bull-item"
            @click="toggle(agent.agent_name || agent.name)"
          >
            <div class="agent-top">
              <span class="agent-name">{{ agent.agent_name || agent.name }}</span>
              <span class="agent-prob bull-prob">
                {{ agent.probability != null ? agent.probability.toFixed(1) + '%' : 'N/A' }}
              </span>
            </div>
            <p
              v-if="expanded.has(agent.agent_name || agent.name)"
              class="agent-reasoning"
            >{{ agent.reasoning }}</p>
            <p v-else class="agent-reasoning-preview">
              {{ truncate(agent.reasoning) }}
            </p>
          </div>
          <div v-if="!bullAgents.length" class="empty-column">No bull agents</div>
        </div>
      </div>

      <!-- VS divider -->
      <div class="vs-divider">
        <div class="vs-badge">VS</div>
      </div>

      <!-- Bear column -->
      <div class="column bear-column">
        <div class="column-header bear-header">
          <span class="column-icon">&#9660;</span>
          <span>Bear ({{ bearAgents.length }})</span>
        </div>
        <div class="agent-list">
          <div
            v-for="agent in bearAgents"
            :key="agent.agent_name || agent.name"
            class="agent-item bear-item"
            @click="toggle(agent.agent_name || agent.name)"
          >
            <div class="agent-top">
              <span class="agent-name">{{ agent.agent_name || agent.name }}</span>
              <span class="agent-prob bear-prob">
                {{ agent.probability != null ? agent.probability.toFixed(1) + '%' : 'N/A' }}
              </span>
            </div>
            <p
              v-if="expanded.has(agent.agent_name || agent.name)"
              class="agent-reasoning"
            >{{ agent.reasoning }}</p>
            <p v-else class="agent-reasoning-preview">
              {{ truncate(agent.reasoning) }}
            </p>
          </div>
          <div v-if="!bearAgents.length" class="empty-column">No bear agents</div>
        </div>
      </div>
    </div>

    <!-- Neutral section -->
    <div v-if="neutralAgents.length" class="neutral-section">
      <div class="column-header neutral-header">
        <span>Neutral ({{ neutralAgents.length }})</span>
      </div>
      <div class="neutral-list">
        <div
          v-for="agent in neutralAgents"
          :key="agent.agent_name || agent.name"
          class="agent-item neutral-item"
          @click="toggle(agent.agent_name || agent.name)"
        >
          <div class="agent-top">
            <span class="agent-name">{{ agent.agent_name || agent.name }}</span>
            <span class="agent-prob neutral-prob">
              {{ agent.probability != null ? agent.probability.toFixed(1) + '%' : 'N/A' }}
            </span>
          </div>
          <p
            v-if="expanded.has(agent.agent_name || agent.name)"
            class="agent-reasoning"
          >{{ agent.reasoning }}</p>
          <p v-else class="agent-reasoning-preview">
            {{ truncate(agent.reasoning) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'

const props = defineProps({
  agents: {
    type: Array,
    default: () => [],
  },
})

const expanded = reactive(new Set())

function toggle(name) {
  if (expanded.has(name)) {
    expanded.delete(name)
  } else {
    expanded.add(name)
  }
}

function truncate(text) {
  if (!text) return ''
  return text.length > 140 ? text.slice(0, 137) + '...' : text
}

function isBull(agent) {
  const s = (agent.stance || '').toLowerCase()
  return s === 'bull' || s === 'bullish' || s === 'yes'
}

function isBear(agent) {
  const s = (agent.stance || '').toLowerCase()
  return s === 'bear' || s === 'bearish' || s === 'no'
}

const bullAgents = computed(() =>
  props.agents
    .filter(isBull)
    .sort((a, b) => (b.probability || 0) - (a.probability || 0))
)

const bearAgents = computed(() =>
  props.agents
    .filter(isBear)
    .sort((a, b) => (a.probability || 0) - (b.probability || 0))
)

const neutralAgents = computed(() =>
  props.agents.filter((a) => !isBull(a) && !isBear(a))
)
</script>

<style scoped>
.bull-bear-split {
  --_surface-0: var(--surface-0, #ffffff);
  --_surface-1: var(--surface-1, #f9fafb);
  --_border-default: var(--border-default, #e5e7eb);
  --_text-primary: var(--text-primary, #111827);
  --_text-secondary: var(--text-secondary, #6b7280);
  --_text-tertiary: var(--text-tertiary, #9ca3af);
  --_radius-md: var(--radius-md, 8px);
  --_radius-lg: var(--radius-lg, 12px);
  --_space-4: var(--space-4, 16px);
  --_space-6: var(--space-6, 24px);
  --_transition-fast: var(--transition-fast, 0.15s ease);

  background: var(--_surface-0);
  border: 1px solid var(--_border-default);
  border-radius: var(--_radius-lg);
  padding: var(--_space-6);
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--_text-primary);
  margin-bottom: var(--_space-4);
}

.split-grid {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: var(--_space-4);
}

.column-header {
  font-size: 13px;
  font-weight: 700;
  padding: 8px 12px;
  border-radius: var(--_radius-md);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.bull-header {
  background: #dcfce7;
  color: #166534;
}

.bear-header {
  background: #fef2f2;
  color: #991b1b;
}

.neutral-header {
  background: var(--_surface-1);
  color: var(--_text-secondary);
}

.column-icon {
  font-size: 10px;
}

.agent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.agent-item {
  padding: 12px;
  border-radius: var(--_radius-md);
  border: 1px solid var(--_border-default);
  cursor: pointer;
  transition: box-shadow var(--_transition-fast);
}

.agent-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.bull-item {
  border-left: 3px solid #22c55e;
}

.bear-item {
  border-left: 3px solid #ef4444;
}

.neutral-item {
  border-left: 3px solid #9ca3af;
}

.agent-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--_text-primary);
}

.agent-prob {
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.bull-prob {
  color: #16a34a;
}

.bear-prob {
  color: #dc2626;
}

.neutral-prob {
  color: var(--_text-secondary);
}

.agent-reasoning {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--_text-secondary);
}

.agent-reasoning-preview {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--_text-tertiary);
}

.vs-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 40px;
}

.vs-badge {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--_surface-1);
  border: 2px solid var(--_border-default);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
  color: var(--_text-tertiary);
}

.empty-column {
  font-size: 13px;
  color: var(--_text-tertiary);
  text-align: center;
  padding: 24px;
}

.neutral-section {
  margin-top: var(--_space-4);
  padding-top: var(--_space-4);
  border-top: 1px solid var(--_border-default);
}

.neutral-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 8px;
}

@media (max-width: 640px) {
  .split-grid {
    grid-template-columns: 1fr;
  }

  .vs-divider {
    padding-top: 0;
    padding-bottom: 0;
  }
}
</style>
