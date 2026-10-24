<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

defineProps({ title: { type: String, required: true }, wide: Boolean })
const emit = defineEmits(['close'])
const box = ref(null)
function onKey(e) { if (e.key === 'Escape') emit('close') }
onMounted(async () => {
  document.addEventListener('keydown', onKey)
  await nextTick()
  box.value?.querySelector('input, select, textarea, button')?.focus()
})
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div ref="box" class="modal card" :class="{ wide }" role="dialog" aria-modal="true" :aria-label="title">
      <div class="row-between head">
        <h2>{{ title }}</h2>
        <button class="icon-btn" aria-label="Close" @click="emit('close')">✕</button>
      </div>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; z-index: 80; background: rgba(15, 20, 35, .4); backdrop-filter: blur(3px); -webkit-backdrop-filter: blur(3px); display: flex; align-items: flex-start; justify-content: center; padding: 6vh 16px; overflow-y: auto; }
.modal { width: 100%; max-width: 520px; box-shadow: var(--shadow-lg); background: color-mix(in srgb, var(--surface-solid) 86%, transparent); }
.modal.wide { max-width: 760px; }
.head h2 { margin: 0; }
.head { margin-bottom: 14px; }
</style>
