<template>
  <div class="min-h-[calc(100vh-56px)] flex items-center justify-center px-6 py-12">
    <div class="w-full max-w-md">
      <!-- Card -->
      <div class="glass-card rounded-2xl p-8 space-y-8">
        <!-- Header -->
        <div class="text-center space-y-2">
          <h1 class="text-3xl font-headline font-bold text-on-surface tracking-tight">
            {{ isRegister ? 'Create Account' : 'Sign In' }}
          </h1>
          <p class="text-sm text-on-surface-variant">
            {{ isRegister ? 'Join DePredict to start predicting' : 'Welcome back to DePredict' }}
          </p>
        </div>

        <!-- Test Mode Banner: credentials are pre-filled with a shared
             premium demo account so visitors can try Premium features
             during the testing phase. Remove before public launch. -->
        <div v-if="!isRegister" class="flex items-start gap-3 px-4 py-3 rounded-xl bg-primary-container/15 border border-primary/30 text-on-surface text-sm">
          <span class="material-symbols-outlined text-base text-primary mt-0.5">science</span>
          <div class="space-y-1">
            <div class="font-semibold text-primary">Test Mode</div>
            <div class="text-xs text-on-surface-variant leading-relaxed">
              A shared Premium demo account has been pre-filled. Just click <strong class="text-on-surface">Sign In</strong> to try every feature for free.
            </div>
          </div>
        </div>

        <!-- Error -->
        <div v-if="error" class="flex items-center gap-3 px-4 py-3 rounded-xl bg-error-container/20 border border-error/20 text-error text-sm">
          <span class="material-symbols-outlined text-lg">error</span>
          <span>{{ error }}</span>
        </div>

        <!-- Form -->
        <form @submit.prevent="handleSubmit" class="space-y-5">
          <div>
            <label class="block text-[0.6875rem] uppercase tracking-[0.12em] text-on-surface-variant font-bold mb-2">Email</label>
            <input
              v-model="email"
              type="email"
              required
              autocomplete="email"
              class="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-lg px-4 py-3 text-on-surface text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label class="block text-[0.6875rem] uppercase tracking-[0.12em] text-on-surface-variant font-bold mb-2">Password</label>
            <input
              v-model="password"
              type="password"
              required
              autocomplete="current-password"
              class="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-lg px-4 py-3 text-on-surface text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
              placeholder="Enter password"
            />
          </div>

          <div v-if="isRegister">
            <label class="block text-[0.6875rem] uppercase tracking-[0.12em] text-on-surface-variant font-bold mb-2">Confirm Password</label>
            <input
              v-model="confirmPassword"
              type="password"
              required
              autocomplete="new-password"
              class="w-full bg-surface-container-lowest border border-outline-variant/40 rounded-lg px-4 py-3 text-on-surface text-sm focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30 transition-all"
              placeholder="Confirm password"
            />
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-primary-container text-on-primary-container px-8 py-3 rounded-xl font-bold font-headline uppercase tracking-[0.08em] hover:scale-[1.02] active:scale-95 transition-all shadow-[0_0_20px_rgba(77,142,255,0.3)] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            {{ loading ? 'Please wait...' : (isRegister ? 'Create Account' : 'Sign In') }}
          </button>
        </form>

        <!-- Toggle -->
        <div class="text-center text-sm text-on-surface-variant">
          <span v-if="isRegister">
            Already have an account?
            <button @click="mode = 'login'" class="text-primary hover:underline font-medium">Sign In</button>
          </span>
          <span v-else>
            Don't have an account?
            <button @click="mode = 'register'" class="text-primary hover:underline font-medium">Create Account</button>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../store/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// Test-mode shared Premium demo account. While the site is in the testing
// phase we pre-fill these credentials so any visitor can sign in with one
// click and exercise Premium features. Remove or gate behind an env flag
// before public launch.
const DEMO_EMAIL = 'demo@depredict.net'
const DEMO_PASSWORD = 'demo1234'

const mode = ref('login')
const email = ref(DEMO_EMAIL)
const password = ref(DEMO_PASSWORD)
const confirmPassword = ref('')
const error = ref(null)
const loading = ref(false)

const isRegister = computed(() => mode.value === 'register')

async function handleSubmit() {
  error.value = null

  if (isRegister.value && password.value !== confirmPassword.value) {
    error.value = 'Passwords do not match'
    return
  }

  loading.value = true
  try {
    if (isRegister.value) {
      await authStore.register(email.value, password.value)
    } else {
      await authStore.login(email.value, password.value)
    }
    const redirect = route.query.redirect || '/analyze'
    router.push(redirect)
  } catch (err) {
    error.value = err.response?.data?.error || err.response?.data?.message || err.message || 'An error occurred'
  } finally {
    loading.value = false
  }
}
</script>
