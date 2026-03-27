import { defineStore } from 'pinia'
import api from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('depredict-token') || null,
    user: JSON.parse(localStorage.getItem('depredict-user') || 'null'),
  }),

  getters: {
    isLoggedIn: (state) => !!state.token,
    isPremium: (state) => state.user?.tier === 'premium',
    predictionsRemaining: (state) => {
      if (!state.user) return 0
      if (state.user.tier === 'premium') return null
      const limit = state.user.monthly_prediction_limit ?? 3
      const used = state.user.predictions_used ?? 0
      return Math.max(0, limit - used)
    },
  },

  actions: {
    _setAuth(token, user) {
      this.token = token
      this.user = user
      if (token) {
        localStorage.setItem('depredict-token', token)
      } else {
        localStorage.removeItem('depredict-token')
      }
      if (user) {
        localStorage.setItem('depredict-user', JSON.stringify(user))
      } else {
        localStorage.removeItem('depredict-user')
      }
    },

    async register(email, password) {
      const response = await api.post('/api/auth/register', { email, password })
      this._setAuth(response.data.token, response.data.user)
      return response.data
    },

    async login(email, password) {
      const response = await api.post('/api/auth/login', { email, password })
      this._setAuth(response.data.token, response.data.user)
      return response.data
    },

    logout() {
      this._setAuth(null, null)
    },

    async fetchMe() {
      try {
        const response = await api.get('/api/auth/me')
        this.user = response.data
        localStorage.setItem('depredict-user', JSON.stringify(response.data))
        return response.data
      } catch (err) {
        if (err.response?.status === 401) {
          this._setAuth(null, null)
        }
        throw err
      }
    },

    async createCheckout() {
      const response = await api.post('/api/auth/create-checkout')
      if (response.data.url) {
        window.location.href = response.data.url
      }
      return response.data
    },

    async openPortal() {
      const response = await api.post('/api/auth/create-portal')
      if (response.data.url) {
        window.location.href = response.data.url
      }
      return response.data
    },
  },
})
