<template>
  <div class="progress-bar-container">
    <div class="progress-header">
      <span class="stage-label" :class="stageClass">{{ stageLabel }}</span>
      <span class="percent-label">{{ percent }}%</span>
    </div>
    <div class="progress-track">
      <div
        class="progress-fill"
        :class="stageClass"
        :style="{ width: percent + '%' }"
      ></div>
    </div>
    <p class="progress-message" v-if="message">{{ message }}</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: { type: String, default: '' },
  percent: { type: Number, default: 0 },
  message: { type: String, default: '' },
})

const stageLabels = {
  initializing: 'Initializing',
  created: 'Created',
  retrieving: 'Retrieving Sources',
  extracting_entities: 'Extracting Entities',
  debating_r1: 'Round 1: Independent Predictions',
  debating_r2: 'Round 2: Cross-Rebuttal',
  debating_r3: 'Round 3: Final Predictions',
  meta_predicting: 'Meta-Predictions',
  aggregating: 'Aggregating Results',
  generating_report: 'Generating Report',
  completed: 'Complete',
  failed: 'Failed',
}

const stageLabel = computed(() => stageLabels[props.stage] || props.stage || 'Waiting')

const stageClass = computed(() => {
  if (props.stage === 'completed') return 'stage-complete'
  if (props.stage === 'failed') return 'stage-failed'
  if (props.stage === 'aggregating' || props.stage === 'generating_report' || props.stage === 'meta_predicting') return 'stage-final'
  if (props.stage?.startsWith('debating_')) return 'stage-debate'
  return 'stage-init'
})
</script>

<style scoped>
.progress-bar-container {
  background: white;
  padding: 16px 20px;
  border-radius: var(--radius);
  border: 1px solid var(--gray-200);
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.stage-label {
  font-size: 13px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 999px;
}

.stage-init {
  background: #e0e7ff;
  color: #3730a3;
}

.stage-debate {
  background: #fef3c7;
  color: #92400e;
}

.stage-final {
  background: #ede9fe;
  color: #5b21b6;
}

.stage-complete {
  background: #dcfce7;
  color: #166534;
}

.stage-failed {
  background: #fef2f2;
  color: #991b1b;
}

.percent-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-700);
}

.progress-track {
  height: 8px;
  background: var(--gray-100);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.progress-fill.stage-init {
  background: #6366f1;
}

.progress-fill.stage-debate {
  background: #f59e0b;
}

.progress-fill.stage-final {
  background: #8b5cf6;
}

.progress-fill.stage-complete {
  background: #22c55e;
}

.progress-fill.stage-failed {
  background: #ef4444;
}

.progress-message {
  margin-top: 8px;
  font-size: 13px;
  color: var(--gray-500);
}
</style>
