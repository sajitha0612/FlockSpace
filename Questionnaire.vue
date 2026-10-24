<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../lib/api'

const emit = defineEmits(['saved'])
const questions = ref([])
const answers = ref({})
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  const d = await api.get('/me/questionnaire')
  questions.value = d.questions
  answers.value = { ...d.answers }
  for (const q of d.questions) if (q.type === 'multi' && !Array.isArray(answers.value[q.id])) answers.value[q.id] = []
})

function toggle(qid, v) {
  const cur = answers.value[qid]
  answers.value[qid] = cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]
}

async function save() {
  error.value = ''
  busy.value = true
  try {
    emit('saved', await api.put('/me/questionnaire', { answers: answers.value }))
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <form class="stack" @submit.prevent="save">
    <fieldset v-for="(q, i) in questions" :key="q.id" class="q">
      <legend><span class="n">{{ i + 1 }}</span> {{ q.text }}</legend>
      <div v-if="q.type === 'scale'" class="scale">
        <span class="small muted">{{ q.labels[0] }}</span>
        <label v-for="v in q.max - q.min + 1" :key="v" class="pill" :class="{ on: answers[q.id] === v + q.min - 1 }">
          <input v-model="answers[q.id]" type="radio" class="sr-only" :name="q.id" :value="v + q.min - 1" />{{ v + q.min - 1 }}
        </label>
        <span class="small muted">{{ q.labels[1] }}</span>
      </div>
      <div v-else class="opts">
        <template v-if="q.type === 'multi'">
          <label v-for="o in q.options" :key="o.value" class="pill" :class="{ on: answers[q.id]?.includes(o.value) }">
            <input type="checkbox" class="sr-only" :checked="answers[q.id]?.includes(o.value)" @change="toggle(q.id, o.value)" />{{ o.label }}
          </label>
        </template>
        <template v-else>
          <label v-for="o in q.options" :key="o.value" class="pill" :class="{ on: answers[q.id] === o.value }">
            <input v-model="answers[q.id]" type="radio" class="sr-only" :name="q.id" :value="o.value" />{{ o.label }}
          </label>
        </template>
      </div>
    </fieldset>
    <p v-if="error" class="notice danger">{{ error }}</p>
    <button class="btn lg" :disabled="busy">Save answers</button>
  </form>
</template>

<style scoped>
.q { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 12px 14px; margin: 0; background: var(--surface); }
legend { font-weight: 800; padding: 0 4px; }
.n { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: var(--primary-soft); color: var(--primary); font-size: .75rem; margin-right: 4px; }
.opts, .scale { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 6px; }
.pill { border: 1px solid var(--border-strong); border-radius: 999px; padding: 6px 14px; cursor: pointer; font-weight: 600; font-size: .9rem; }
.pill.on { background: var(--primary); color: var(--primary-ink); border-color: var(--primary); }
.pill:focus-within { outline: 3px solid var(--focus); outline-offset: 2px; }
</style>
