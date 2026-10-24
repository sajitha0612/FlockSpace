<script setup>
import Bird from './Bird.vue'

defineProps({
  loading: Boolean,
  error: { type: Object, default: null },
  empty: Boolean,
  emptyText: { type: String, default: 'Nothing here yet.' },
  hasData: { type: Boolean, default: true },
})
defineEmits(['retry'])
</script>

<template>
  <div v-if="error && !hasData" class="state" role="alert">
    <Bird :size="64" mood="sad" label="" />
    <p><strong>Couldn't load this.</strong><br /><span class="muted">{{ error.message }}</span></p>
    <button class="btn secondary sm" @click="$emit('retry')">Try again</button>
  </div>
  <div v-else-if="loading && !hasData" class="state" aria-busy="true">
    <Bird :size="56" mood="thinking" label="" />
    <p class="muted">Loading…</p>
  </div>
  <div v-else-if="empty" class="state">
    <slot name="empty"><p class="muted">{{ emptyText }}</p></slot>
  </div>
  <template v-else>
    <div v-if="error" class="notice danger small" role="alert">Couldn't refresh: {{ error.message }} <button class="btn ghost sm" @click="$emit('retry')">Retry</button></div>
    <slot />
  </template>
</template>

<style scoped>
.state { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 8px; padding: 28px 12px; }
</style>
