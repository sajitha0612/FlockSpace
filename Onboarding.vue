<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Bird from '../components/Bird.vue'
import ProfileForm from '../components/ProfileForm.vue'
import Questionnaire from '../components/Questionnaire.vue'
import { api } from '../lib/api'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const step = ref(1)

async function done() {
  session.user = await api.get('/auth/me')
  session.toast('All set. Welcome to the flock!', 'ok')
  router.replace('/home')
}
</script>

<template>
  <div class="page narrow">
    <div class="row head">
      <Bird :size="80" :mood="step === 2 ? 'thinking' : 'happy'" label="" />
      <div>
        <p class="muted small">Step {{ step }} of 2</p>
        <h1>{{ step === 1 ? 'Tell us about your studies' : 'How do you like to study?' }}</h1>
        <p class="muted">{{ step === 1 ? 'Used to suggest rooms and study buddies. You can change it any time.' : 'Ten quick questions. Your answers shape buddy matching and are never shown as a score to others.' }}</p>
      </div>
    </div>
    <p class="skip small"><RouterLink to="/home">Skip for now</RouterLink> · you can finish this any time from Home or Settings.</p>
    <div class="card">
      <ProfileForm v-if="step === 1" submit-label="Continue" @saved="step = 2" />
      <Questionnaire v-else @saved="done" />
    </div>
  </div>
</template>

<style scoped>
.narrow { max-width: 760px; }
.head { flex-wrap: nowrap; margin-bottom: 16px; }
.head h1 { margin: 0; }
.head p { margin: 2px 0; }
.skip { margin: -6px 0 12px; }
</style>
