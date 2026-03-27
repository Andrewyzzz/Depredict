<template>
  <div class="max-w-4xl mx-auto px-6 py-12 font-body">

    <!-- Header -->
    <section class="text-center space-y-2 mb-16">
      <h1 class="text-4xl font-headline font-bold text-on-surface tracking-tight">Pricing</h1>
      <p class="text-on-surface-variant text-lg max-w-xl mx-auto leading-relaxed">
        Choose the plan that fits your prediction needs.
      </p>
    </section>

    <!-- Pricing Cards -->
    <div class="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto">

      <!-- Free Tier -->
      <div class="glass-card rounded-2xl p-10 space-y-8 flex flex-col">
        <div>
          <h2 class="font-headline font-bold text-on-surface text-xl">Free</h2>
          <p class="text-4xl font-headline font-bold text-on-surface mt-3">$0<span class="text-base text-on-surface-variant font-normal">/mo</span></p>
          <p class="text-sm text-on-surface-variant mt-2">Get started with limited access</p>
        </div>

        <ul class="space-y-4 text-sm text-on-surface-variant flex-1">
          <li class="flex items-center gap-3">
            <span class="material-symbols-outlined text-secondary text-base">check</span>
            Full prediction history
          </li>
          <li class="flex items-center gap-3">
            <span class="material-symbols-outlined text-secondary text-base">check</span>
            3 predictions per month
          </li>
          <li class="flex items-center gap-3">
            <span class="material-symbols-outlined text-on-surface-variant/40 text-base">close</span>
            <span class="text-on-surface-variant/60">Market Scanner</span>
          </li>
          <li class="flex items-center gap-3">
            <span class="material-symbols-outlined text-on-surface-variant/40 text-base">close</span>
            <span class="text-on-surface-variant/60">Unlimited predictions</span>
          </li>
        </ul>

        <router-link
          to="/login"
          class="w-full py-3 rounded-xl border border-outline-variant/40 text-on-surface font-bold font-headline uppercase tracking-[0.08em] hover:bg-white/5 transition-all text-center block"
        >
          Get Started
        </router-link>
      </div>

      <!-- Premium Tier -->
      <div class="glass-card rounded-2xl p-10 space-y-8 flex flex-col border-primary/30 relative overflow-hidden">
        <div class="absolute top-0 right-0 bg-primary-container text-on-primary-container px-4 py-1 rounded-bl-lg text-[10px] font-black uppercase tracking-widest">Most Popular</div>

        <div>
          <h2 class="font-headline font-bold text-primary text-xl">Premium</h2>
          <p class="text-4xl font-headline font-bold text-on-surface mt-3">$50<span class="text-base text-on-surface-variant font-normal">/mo</span></p>
          <p class="text-sm text-on-surface-variant mt-2">Full access to the prediction engine</p>
        </div>

        <ul class="space-y-4 text-sm text-on-surface-variant flex-1">
          <li class="flex items-center gap-3">
            <span class="material-symbols-outlined text-secondary text-base">check</span>
            Full prediction history
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

        <router-link
          to="/login?redirect=/account"
          class="w-full py-3 rounded-xl bg-primary-container text-on-primary-container font-bold font-headline uppercase tracking-[0.08em] hover:scale-[1.02] active:scale-95 transition-all shadow-[0_0_20px_rgba(77,142,255,0.3)] text-center block"
        >
          Subscribe
        </router-link>
      </div>

    </div>

  </div>
</template>

<script setup>
</script>
