<template>
  <div class="max-w-3xl mx-auto px-6 py-12 font-body">

    <!-- Header -->
    <section class="text-center space-y-2 mb-12">
      <h1 class="text-4xl font-headline font-bold text-on-surface tracking-tight">Account</h1>
      <p class="text-on-surface-variant font-label text-sm uppercase tracking-[0.1em]">Manage your subscription</p>
    </section>

    <!-- Account Card -->
    <div class="glass-card rounded-2xl p-8 space-y-8 mb-12">
      <!-- User Info -->
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div class="flex items-center gap-4">
          <div class="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
            <span class="material-symbols-outlined">person</span>
          </div>
          <div>
            <p class="font-headline font-bold text-on-surface">{{ authStore.user?.email }}</p>
            <p class="text-xs text-on-surface-variant">Member</p>
          </div>
        </div>
        <span
          class="px-4 py-1.5 rounded-full text-xs font-black uppercase tracking-widest border"
          :class="authStore.isPremium
            ? 'bg-secondary/10 text-secondary border-secondary/20'
            : 'bg-surface-container-highest text-on-surface-variant border-outline-variant/30'"
        >
          {{ authStore.isPremium ? 'Premium' : 'Free' }}
        </span>
      </div>

      <!-- Usage (free tier) -->
      <div v-if="!authStore.isPremium" class="space-y-3">
        <div class="flex items-center justify-between text-sm">
          <span class="text-on-surface-variant">Predictions this month</span>
          <span class="font-headline font-bold text-on-surface tabular-nums">
            {{ authStore.user?.predictions_used ?? 0 }} / {{ authStore.user?.monthly_prediction_limit ?? 3 }}
          </span>
        </div>
        <div class="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden">
          <div
            class="h-full bg-primary transition-all duration-300 rounded-full"
            :style="{ width: usagePercent + '%' }"
          ></div>
        </div>
      </div>

      <!-- Actions -->
      <div class="flex flex-wrap gap-4">
        <button
          v-if="!authStore.isPremium"
          @click="handleCheckout"
          :disabled="checkoutLoading"
          class="bg-primary-container text-on-primary-container px-8 py-3 rounded-xl font-bold font-headline uppercase tracking-[0.08em] hover:scale-[1.02] active:scale-95 transition-all shadow-[0_0_20px_rgba(77,142,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {{ checkoutLoading ? 'Redirecting...' : 'Upgrade to Premium — $50/mo' }}
        </button>

        <button
          v-if="authStore.isPremium"
          @click="handlePortal"
          :disabled="portalLoading"
          class="bg-primary-container text-on-primary-container px-8 py-3 rounded-xl font-bold font-headline uppercase tracking-[0.08em] hover:scale-[1.02] active:scale-95 transition-all shadow-[0_0_20px_rgba(77,142,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {{ portalLoading ? 'Redirecting...' : 'Manage Subscription' }}
        </button>

        <button
          @click="handleLogout"
          class="px-8 py-3 rounded-xl border border-outline-variant/40 text-on-surface-variant font-bold font-headline uppercase tracking-[0.08em] hover:bg-white/5 hover:text-on-surface transition-all"
        >
          Logout
        </button>
      </div>

      <!-- Error -->
      <div v-if="error" class="flex items-center gap-3 px-4 py-3 rounded-xl bg-error-container/20 border border-error/20 text-error text-sm">
        <span class="material-symbols-outlined text-lg">error</span>
        <span>{{ error }}</span>
      </div>
    </div>

    <!-- Tier Comparison -->
    <section class="space-y-6">
      <h2 class="text-xl font-headline font-bold text-on-surface tracking-tight text-center">Plan Comparison</h2>
      <div class="grid md:grid-cols-2 gap-6">
        <!-- Free Tier -->
        <div class="glass-card rounded-xl p-8 space-y-6">
          <div>
            <h3 class="font-headline font-bold text-on-surface text-lg">Free</h3>
            <p class="text-3xl font-headline font-bold text-on-surface mt-2">$0<span class="text-sm text-on-surface-variant font-normal">/mo</span></p>
          </div>
          <ul class="space-y-3 text-sm text-on-surface-variant">
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-secondary text-base">check</span>
              Full prediction history access
            </li>
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-secondary text-base">check</span>
              3 predictions per month
            </li>
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-on-surface-variant/40 text-base">close</span>
              <span class="text-on-surface-variant/60">Market Scanner access</span>
            </li>
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-on-surface-variant/40 text-base">close</span>
              <span class="text-on-surface-variant/60">Unlimited predictions</span>
            </li>
          </ul>
        </div>

        <!-- Premium Tier -->
        <div class="glass-card rounded-xl p-8 space-y-6 border-primary/30 relative overflow-hidden">
          <div class="absolute top-0 right-0 bg-primary-container text-on-primary-container px-4 py-1 rounded-bl-lg text-[10px] font-black uppercase tracking-widest">Recommended</div>
          <div>
            <h3 class="font-headline font-bold text-primary text-lg">Premium</h3>
            <p class="text-3xl font-headline font-bold text-on-surface mt-2">$50<span class="text-sm text-on-surface-variant font-normal">/mo</span></p>
          </div>
          <ul class="space-y-3 text-sm text-on-surface-variant">
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-secondary text-base">check</span>
              Full prediction history access
            </li>
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-secondary text-base">check</span>
              Unlimited predictions
            </li>
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-secondary text-base">check</span>
              Market Scanner access
            </li>
            <li class="flex items-center gap-3">
              <span class="material-symbols-outlined text-secondary text-base">check</span>
              Priority analysis queue
            </li>
          </ul>
        </div>
      </div>
    </section>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'

const router = useRouter()
const authStore = useAuthStore()

const checkoutLoading = ref(false)
const portalLoading = ref(false)
const error = ref(null)

const usagePercent = computed(() => {
  const limit = authStore.user?.monthly_prediction_limit ?? 3
  const used = authStore.user?.predictions_used ?? 0
  return Math.min(100, (used / limit) * 100)
})

async function handleCheckout() {
  checkoutLoading.value = true
  error.value = null
  try {
    await authStore.createCheckout()
  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'Failed to create checkout session'
  } finally {
    checkoutLoading.value = false
  }
}

async function handlePortal() {
  portalLoading.value = true
  error.value = null
  try {
    await authStore.openPortal()
  } catch (err) {
    error.value = err.response?.data?.error || err.message || 'Failed to open billing portal'
  } finally {
    portalLoading.value = false
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/')
}
</script>
