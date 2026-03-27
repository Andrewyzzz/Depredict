import { createRouter, createWebHistory } from 'vue-router'

import HomePage from '../views/HomePage.vue'
import AnalyzeView from '../views/DebateView.vue'
import MarketScanView from '../views/MarketScanView.vue'
import HistoryView from '../views/HistoryView.vue'
import ReportView from '../views/ReportView.vue'
import MarketDetailView from '../views/MarketDetailView.vue'
import LoginView from '../views/LoginView.vue'
import AccountView from '../views/AccountView.vue'
import PricingView from '../views/PricingView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomePage,
  },
  {
    path: '/analyze',
    name: 'Analyze',
    component: AnalyzeView,
    meta: { requiresAuth: true },
  },
  {
    path: '/scan',
    name: 'MarketScan',
    component: MarketScanView,
    meta: { requiresAuth: true, requiresPremium: true },
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView,
  },
  {
    path: '/market/:slug',
    name: 'MarketDetail',
    component: MarketDetailView,
  },
  {
    path: '/report/:taskId',
    name: 'Report',
    component: ReportView,
  },
  {
    path: '/login',
    name: 'Login',
    component: LoginView,
    meta: { guest: true },
  },
  {
    path: '/account',
    name: 'Account',
    component: AccountView,
    meta: { requiresAuth: true },
  },
  {
    path: '/pricing',
    name: 'Pricing',
    component: PricingView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('depredict-token')

  if (to.meta.requiresAuth && !token) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  if (to.meta.guest && token) {
    return next('/analyze')
  }

  next()
})

export default router
