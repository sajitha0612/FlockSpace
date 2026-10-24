<script setup>
import { ref } from 'vue'

const model = defineModel({ type: Array, default: () => [] })
const props = defineProps({ placeholder: { type: String, default: 'Type and press Enter' }, max: { type: Number, default: 30 }, label: { type: String, default: '' } })
const draft = ref('')

function add() {
  const v = draft.value.trim()
  if (v && !model.value.some((x) => x.toLowerCase() === v.toLowerCase()) && model.value.length < props.max) model.value = [...model.value, v]
  draft.value = ''
}
function remove(i) {
  model.value = model.value.filter((_, j) => j !== i)
}
function onKey(e) {
  if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() }
  else if (e.key === 'Backspace' && !draft.value && model.value.length) remove(model.value.length - 1)
}
</script>

<template>
  <div class="tags">
    <span v-for="(t, i) in model" :key="t" class="chip primary">{{ t }}<button type="button" :aria-label="`Remove ${t}`" @click="remove(i)">✕</button></span>
    <input v-model="draft" class="tag-input" :placeholder="placeholder" :aria-label="label || placeholder" @keydown="onKey" @blur="add" />
  </div>
</template>

<style scoped>
.tags { display: flex; flex-wrap: wrap; gap: 6px; padding: 7px; border: 1px solid var(--border-strong); border-radius: var(--radius-sm); background: var(--surface); }
.tag-input { flex: 1; min-width: 140px; border: 0; outline: 0; font: inherit; background: transparent; color: var(--ink); padding: 3px; }
</style>
