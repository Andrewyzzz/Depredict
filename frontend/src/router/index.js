import { createRouter, createWebHistory } from 'vue-router'

import HomePage from '../views/HomePage.vue'
import AnalyzeView from '../views/DebateView.vue'
import MarketScanView from '../views/MarketScanView.vue'
import HistoryView from '../views/HistoryView.vue'
import ReportView from '../views/ReportView.vue'

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
  },
  {
    path: '/scan',
    name: 'MarketScan',
    component: MarketScanView,
  },
  {
    path: '/history',
    name: 'History',
    component: HistoryView,
  },
  {
    path: '/report/:taskId',
    name: 'Report',
    component: ReportView,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
