import { defineStore } from 'pinia'
import api from '../api/client'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    theme: localStorage.getItem('depredict-theme') || 'dark',
  }),

  actions: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('depredict-theme', this.theme)
      document.documentElement.setAttribute('data-theme', this.theme)
    },

    initTheme() {
      document.documentElement.setAttribute('data-theme', this.theme)
    },
  },
})

export const useDebateStore = defineStore('debate', {
  state: () => ({
    currentTask: null,
    taskId: null,
    tasks: [],
    eventSource: null,
    isLoading: false,
    error: null,
    progress: {
      stage: '',
      percent: 0,
      message: '',
    },
    // Real-time agent results as they come in
    agentResults: [],
    aggregation: null,
    fullResult: null,
    // Preserve question/price so DebateView can display them after navigation
    currentQuestion: '',
    currentMarketPrice: null,
    currentEndDate: null,
  }),

  getters: {
    isComplete: (state) => state.progress.stage === 'completed',
    isFailed: (state) => state.progress.stage === 'failed',
    isRunning: (state) => state.taskId && !['completed', 'failed', ''].includes(state.progress.stage),
  },

  actions: {
    async startDebate(question, marketPrice = null, slug = null, endDate = null) {
      this.isLoading = true
      this.error = null
      this.agentResults = []
      this.aggregation = null
      this.fullResult = null
      this.progress = { stage: 'initializing', percent: 0, message: 'Starting...' }
      this.currentQuestion = question
      this.currentMarketPrice = marketPrice
      this.currentEndDate = endDate

      try {
        const response = await api.post('/api/debate/start', {
          question,
          market_price: marketPrice,
          slug: slug,
        })
        this.taskId = response.data.task_id
        this.currentTask = response.data
        this.subscribeToProgress(this.taskId)
        return response.data
      } catch (err) {
        this.error = err.response?.data?.error || err.message
        this.isLoading = false
        throw err
      }
    },

    subscribeToProgress(taskId) {
      if (this.eventSource) {
        this.eventSource.close()
      }

      const baseUrl = import.meta.env.VITE_API_URL || ''
      this.eventSource = new EventSource(`${baseUrl}/api/debate/${taskId}/stream`)

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          // Update progress
          this.progress = {
            stage: data.stage || '',
            percent: data.percent || 0,
            message: data.message || '',
          }

          // Collect agent results as they arrive
          if (data.agent_name && data.data) {
            this.agentResults.push({
              name: data.agent_name,
              stage: data.stage,
              ...data.data,
            })
          }

          // Handle completion
          if (data.stage === 'completed') {
            this.isLoading = false
            if (data.data) {
              this.fullResult = data.data
              this.aggregation = data.data.aggregation_mechanisms || null
            }
            // Fetch full result
            this.fetchResult(taskId)
            this._closeSSE()
          }

          // Handle failure
          if (data.stage === 'failed') {
            this.error = data.message
            this.isLoading = false
            this._closeSSE()
          }
        } catch (e) {
          // Ignore parse errors (heartbeats etc)
        }
      }

      this.eventSource.onerror = () => {
        // Connection error - check task status via polling
        this._closeSSE()
        this.pollStatus(taskId)
      }
    },

    async fetchResult(taskId) {
      try {
        const r = await api.get(`/api/debate/${taskId}/result`)
        this.fullResult = r.data
        this.aggregation = r.data.aggregation_mechanisms || null
      } catch (err) {
        // Result may not be ready yet
      }
    },

    async pollStatus(taskId) {
      try {
        const r = await api.get(`/api/debate/${taskId}/status`)
        const data = r.data
        this.progress = {
          stage: data.current_stage,
          percent: data.progress_percent,
          message: data.progress_message,
        }
        if (data.status === 'COMPLETED') {
          this.isLoading = false
          this.fetchResult(taskId)
        } else if (data.status === 'FAILED') {
          this.error = data.error
          this.isLoading = false
        }
      } catch (err) {
        this.error = 'Lost connection to server'
        this.isLoading = false
      }
    },

    async fetchHistory() {
      try {
        const response = await api.get('/api/history')
        return response.data
      } catch (err) {
        this.error = err.response?.data?.error || err.message
        throw err
      }
    },

    async fetchCalibration() {
      const response = await api.get('/api/history/calibration')
      return response.data
    },

    async fetchAgentRankings() {
      const response = await api.get('/api/history/agents')
      return response.data
    },

    async fetchMarkets(category = null, limit = 50) {
      const params = { limit }
      if (category) params.category = category
      const response = await api.get('/api/market/active', { params })
      return response.data
    },

    async fetchMarketScan(category = null) {
      const params = {}
      if (category) params.category = category
      const response = await api.get('/api/market/scan', { params })
      return response.data
    },

    _closeSSE() {
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
    },

    cleanup() {
      this._closeSSE()
      this.isLoading = false
    },
  },
})
