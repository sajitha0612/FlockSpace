<script setup>
import { computed, ref } from 'vue'
import Bird from '../components/Bird.vue'
import Nest from '../components/Nest.vue'
import Icon from '../components/Icon.vue'
import StateBlock from '../components/StateBlock.vue'
import { api } from '../lib/api'
import { ID_ACCEPT, ID_MAX_MB, useIdCard } from '../lib/idcard'
import { ago, when } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { useSession } from '../stores/session'

const session = useSession()
const { busy, run } = useAction(session)
const prof = useLoad(() => api.get('/me/profile'))
const items = useLoad(() => api.get('/me/items'))
const ledger = useLoad(() => api.get('/me/ledger'))
const slot = ref('color')
const preview = ref(null)
const mood = ref('idle')
const SLOTS = [['color', 'Bird'], ['accessory', 'Accessories'], ['outfit', 'Outfits'], ['frame', 'Frames'], ['nest', 'Nest'], ['animation', 'Victory animation']]
const bird = computed(() => items.data.value?.bird || session.user.bird)
const shown = computed(() => ({ ...bird.value, ...(preview.value ? { [preview.value.slot]: preview.value.id } : {}) }))
const slotItems = computed(() => (items.data.value?.items || []).filter((i) => i.slot === slot.value))

async function equip(item) {
  const b = await run(() => api.put('/me/bird', { slot: item.slot, item_id: item.id }), `Equipped ${item.name}.`)
  items.data.value.bird = b
  session.user.bird = b
  mood.value = 'happy'
  setTimeout(() => (mood.value = 'idle'), 1500)
}
async function unequip(s) {
  const b = await run(() => api.put('/me/bird', { slot: s, item_id: null }))
  items.data.value.bird = b
  session.user.bird = b
}
async function buy(item) {
  if (!confirm(`Spend ${item.price} twigs on ${item.name}?`)) return
  await run(() => api.post(`/me/items/${item.id}/buy`), `Unlocked ${item.name}!`)
  items.reload()
  ledger.reload()
}
const id = useIdCard(session.user.id)
const idPicker = ref(null)
const idError = ref('')
async function uploadId(e) {
  const f = e.target.files[0]
  e.target.value = ''
  if (!f) return
  idError.value = ''
  try {
    await id.upload(f)
    session.toast('Student ID verified!', 'ok')
  } catch (err) {
    idError.value = err.message
  }
}
function removeId() {
  if (confirm('Remove your student ID? Your profile will no longer show the verified badge.')) id.remove()
}

function lockText(i) {
  if (i.price) return `${i.price} twigs`
  if (i.golden_required) return `${i.progress}/${i.golden_required} Golden Nests`
  return 'Locked'
}
</script>

<template>
  <div class="page">
    <StateBlock :loading="prof.loading.value" :error="prof.error.value" :has-data="!!prof.data.value" @retry="prof.reload">
      <template v-if="prof.data.value">
        <section class="card head">
          <Bird :bird="shown" :size="120" framed :mood="mood" label="Your bird" />
          <div class="grow">
            <div class="row name-row">
              <h1>{{ prof.data.value.user.name }}</h1>
              <span v-if="id.card.value?.status === 'verified'" class="chip leaf" title="Student ID verified (demo)"><Icon name="check" :size="13" /> Verified student</span>
            </div>
            <p class="muted">{{ prof.data.value.profile.subjects.join(', ') }}<template v-if="prof.data.value.profile.year"> · Year {{ prof.data.value.profile.year }}</template></p>
            <div class="row-between small"><span>Nest level {{ prof.data.value.rewards.nest.level }}</span><span class="mono">{{ prof.data.value.rewards.nest.progress }} / {{ prof.data.value.rewards.nest.target }}</span></div>
            <div class="bar"><span :style="{ width: prof.data.value.rewards.nest.percent + '%' }" /></div>
            <div class="row small stats">
              <span class="chip twig"><Icon name="twig" :size="14" /> {{ prof.data.value.rewards.twigs }} twigs to spend</span>
              <span class="chip gold">{{ prof.data.value.rewards.golden_nests }} Golden Nests</span>
              <span class="chip leaf">{{ prof.data.value.streak.current }}-day streak</span>
            </div>
          </div>
          <RouterLink to="/settings" class="btn secondary sm">Edit profile</RouterLink>
        </section>

        <div class="grid two">
          <section class="card nest">
            <h3>My nest</h3>
            <Nest :progress="prof.data.value.rewards.nest.percent" :skin="shown.nest" :size="220" />
            <p class="small muted">Your nest grows with every twig you earn from quizzes. Each full nest is a new level.</p>
          </section>
          <section class="card">
            <h3>Customize</h3>
            <div class="tabs" role="tablist"><button v-for="s in SLOTS" :key="s[0]" :class="{ on: slot === s[0] }" role="tab" @click="slot = s[0]; preview = null">{{ s[1] }}</button></div>
            <StateBlock :loading="items.loading.value" :error="items.error.value" :has-data="!!items.data.value" @retry="items.reload">
              <div class="items">
                <div v-for="i in slotItems" :key="i.id" class="item-card" :class="{ equipped: bird[i.slot] === i.id, locked: !i.owned }" @mouseenter="preview = i" @mouseleave="preview = null" @focusin="preview = i">
                  <div class="pv">
                    <Nest v-if="i.slot === 'nest'" :progress="100" :skin="i.id" :size="90" :label="i.name" />
                    <Bird v-else :bird="{ ...bird, [i.slot]: i.id }" :size="70" :framed="i.slot === 'frame'" :mood="i.slot === 'animation' ? 'achievement' : 'idle'" :label="i.name" />
                  </div>
                  <strong class="small">{{ i.name }}</strong>
                  <button v-if="bird[i.slot] === i.id && ['accessory', 'outfit'].includes(i.slot)" class="btn ghost sm" :disabled="busy" @click="unequip(i.slot)">Take off</button>
                  <span v-else-if="bird[i.slot] === i.id" class="chip leaf">Equipped</span>
                  <button v-else-if="i.owned" class="btn sm" :disabled="busy" @click="equip(i)">Equip</button>
                  <button v-else-if="i.can_buy" class="btn secondary sm" :disabled="busy" @click="buy(i)">Buy · {{ i.price }}</button>
                  <span v-else class="chip"><Icon name="lock" :size="12" /> {{ lockText(i) }}</span>
                </div>
              </div>
            </StateBlock>
          </section>
        </div>

        <section class="card id-card">
          <div class="card-title"><h3>Student ID</h3><span v-if="id.card.value?.status === 'verified'" class="chip leaf"><Icon name="check" :size="13" /> Verified</span></div>
          <input ref="idPicker" type="file" :accept="ID_ACCEPT" class="sr-only" tabindex="-1" @change="uploadId" />
          <div v-if="!id.card.value" class="id-empty">
            <div class="id-art" aria-hidden="true"><Icon name="idcard" :size="40" /></div>
            <div class="grow">
              <p>Upload a photo of your college ID card to get a <strong>Verified student</strong> badge on your profile.</p>
              <button class="btn" @click="idPicker.click()"><Icon name="upload" :size="17" /> Upload ID card</button>
              <p class="tiny muted">PNG, JPG, WebP or PDF, up to {{ ID_MAX_MB }} MB.</p>
            </div>
          </div>
          <div v-else class="id-row">
            <img v-if="id.card.value.thumb" :src="id.card.value.thumb" alt="Your uploaded student ID" class="id-thumb" />
            <div v-else class="id-art" aria-hidden="true"><Icon name="file" :size="34" /></div>
            <div class="grow">
              <strong>{{ id.card.value.name }}</strong>
              <div v-if="id.card.value.status === 'checking'" class="small">
                <p class="checking">Checking your ID…</p>
                <div class="bar leaf indeterminate"><span /></div>
              </div>
              <p v-else class="small ok-text"><Icon name="check" :size="14" /> Verified {{ when(id.card.value.verified_at) }}</p>
              <div class="row">
                <button class="btn secondary sm" :disabled="id.card.value.status === 'checking'" @click="idPicker.click()">Replace</button>
                <button class="btn ghost sm" :disabled="id.card.value.status === 'checking'" @click="removeId">Remove</button>
              </div>
            </div>
          </div>
          <p v-if="idError" class="small fail">{{ idError }}</p>
          <p class="tiny muted demo-note">Demo verification: your card stays in this browser and is approved automatically. In a real launch a reviewer would check it.</p>
        </section>

        <section class="card">
          <h3>Twig history</h3>
          <div v-if="!ledger.data.value?.entries.length" class="empty small">Earn twigs by answering quiz questions correctly.</div>
          <table v-else class="table">
            <thead><tr><th>When</th><th>What</th><th class="num">Twigs</th></tr></thead>
            <tbody><tr v-for="(e, i) in ledger.data.value.entries" :key="i"><td>{{ ago(e.created_at) }}</td><td>{{ e.note || e.kind }}</td><td class="num" :class="e.amount < 0 ? 'neg' : 'pos'">{{ e.amount > 0 ? '+' : '' }}{{ e.amount }}</td></tr></tbody>
          </table>
        </section>
      </template>
    </StateBlock>
  </div>
</template>

<style scoped>
.head { display: flex; gap: 18px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.head h1 { margin: 0; }
.grow { flex: 1; min-width: 220px; }
.stats { margin-top: 10px; }
.two { grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); margin-bottom: 16px; }
.nest { display: flex; flex-direction: column; align-items: center; text-align: center; }
.items { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 12px; }
.item-card { border: 1px solid var(--border); border-radius: 14px; padding: 10px; display: flex; flex-direction: column; align-items: center; gap: 6px; text-align: center; }
.item-card.equipped { border-color: var(--leaf); box-shadow: 0 0 0 2px var(--leaf-soft); }
.item-card.locked .pv { opacity: .5; filter: grayscale(.6); }
.pv { height: 80px; display: grid; place-items: center; }
.name-row { gap: 10px; }
.id-card { margin-bottom: 16px; }
.id-empty, .id-row { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.id-empty p { margin: 0 0 10px; }
.id-art { width: 120px; height: 76px; border-radius: 12px; display: grid; place-items: center; color: var(--muted); border: 2px dashed var(--border-strong); flex: none; }
.id-thumb { width: 120px; height: 76px; object-fit: cover; border-radius: 12px; border: 1px solid var(--border); flex: none; }
.checking { margin: 4px 0 6px; color: var(--ink-2); }
.indeterminate { width: min(260px, 100%); margin-bottom: 10px; }
.indeterminate > span { width: 40%; animation: slide 1.1s ease-in-out infinite; }
@keyframes slide { from { transform: translateX(-100%); } to { transform: translateX(250%); } }
.ok-text { color: var(--leaf); font-weight: 700; display: flex; align-items: center; gap: 4px; margin: 4px 0 8px; }
.fail { color: var(--danger); margin: 8px 0 0; }
.demo-note { margin: 12px 0 0; }
.neg { color: var(--danger); }
.pos { color: var(--leaf); }
@media (max-width: 860px) { .two { grid-template-columns: 1fr; } }
</style>
