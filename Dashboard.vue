<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import Bird from '../components/Bird.vue'
import Nest from '../components/Nest.vue'
import Icon from '../components/Icon.vue'
import StateBlock from '../components/StateBlock.vue'
import RoomCard from '../components/RoomCard.vue'
import BarChart from '../components/charts/BarChart.vue'
import Heatmap from '../components/charts/Heatmap.vue'
import { api } from '../lib/api'
import { hms, remaining, useNow, when, ago } from '../lib/time'
import { useAction, useLoad } from '../lib/useLoad'
import { withExampleAnalytics, withExampleStreak } from '../lib/exampleData'
import { useSession } from '../stores/session'

const session = useSession()
const router = useRouter()
const { data, loading, error, reload } = useLoad(async () => { const d = await api.get('/dashboard'); return { ...d, streak: withExampleStreak(d.streak) } })
const online = useLoad(() => api.get('/buddies/studying-now'))
const ONLINE = { studying: ['leaf', 'Studying'], break: ['gold', 'On a break'], available: ['primary', 'Online'] }
const week = useLoad(async () => withExampleAnalytics(await api.get('/me/analytics?range=week')))
const now = useNow()
const { busy, run } = useAction(session)

const greeting = computed(() => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'
})
const streakMsg = computed(() => {
  const s = data.value?.streak
  if (!s) return ''
  if (s.today_met) return s.current > 1 ? `Goal met today: ${s.current} days in a row!` : 'Goal met today. Nice work!'
  const left = Math.max(0, s.goal_minutes - s.today_minutes)
  return s.current ? `${left} more focus minutes today keeps your ${s.current}-day streak going.` : `${left} focus minutes today starts a new streak.`
})
const dayLabel = (iso) => new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short' })
const ord = (n) => (n ? `${n}${['th', 'st', 'nd', 'rd'][(n % 100 > 10 && n % 100 < 14) ? 0 : n % 10 < 4 ? n % 10 : 0]}` : 'Unranked')

async function join(room) {
  await run(() => api.post(`/rooms/${room.id}/join`), `Joined ${room.title}`)
  router.push(`/rooms/${room.id}`)
}
async function follow(u) {
  await run(() => api.post(`/users/${u.user_id}/follow`), `Following ${u.name}`)
  reload()
}
</script>

<template>
  <div class="page">
    <StateBlock :loading="loading" :error="error" :has-data="!!data" @retry="reload">
      <template v-if="data">
        <div class="page-head">
          <div>
            <h1>{{ greeting }}, {{ data.user.name.split(' ')[0] }}!</h1>
            <p>Small steps. Big nests.</p>
          </div>
          <div class="row">
            <RouterLink v-if="data.pending_requests" to="/buddies?tab=requests" class="chip primary">{{ data.pending_requests }} buddy request{{ data.pending_requests > 1 ? 's' : '' }}</RouterLink>
            <RouterLink v-if="data.pending_invites" to="/invites" class="chip leaf">{{ data.pending_invites }} room invite{{ data.pending_invites > 1 ? 's' : '' }}</RouterLink>
            <RouterLink to="/rooms/new" class="btn"><Icon name="plus" :size="18" /> Create room</RouterLink>
          </div>
        </div>

        <p v-if="!session.user.onboarded" class="notice warn">
          Finish setting up your profile so we can suggest rooms and study buddies that fit you.
          <RouterLink to="/welcome">Finish setup</RouterLink>
        </p>

        <div class="grid grid-3 top">
          <section class="card nest-card">
            <Bird :bird="data.user.bird" :size="84" mood="idle" label="Your bird" />
            <div class="grow">
              <div class="row-between"><strong>Nest level {{ data.rewards.nest.level }}</strong><span class="chip twig"><Icon name="twig" :size="14" /> {{ data.rewards.twigs }} twigs</span></div>
              <div class="bar twig" :aria-label="`Nest ${data.rewards.nest.percent}% to next level`"><span :style="{ width: data.rewards.nest.percent + '%' }" /></div>
              <p class="small muted">{{ data.rewards.nest.progress }} / {{ data.rewards.nest.target }} twigs to the next level</p>
            </div>
          </section>
          <section class="card golden">
            <Nest :progress="100" skin="nest_golden" :size="90" label="Golden Nest" />
            <div class="grow">
              <strong>Golden Nests</strong>
              <div class="big">{{ data.rewards.golden_nests }}</div>
              <p v-if="data.rewards.next_milestone" class="small muted">{{ data.rewards.next_milestone.remaining }} more to unlock <strong>{{ data.rewards.next_milestone.name }}</strong></p>
              <p v-else class="small muted">Every milestone unlocked!</p>
            </div>
          </section>
          <section class="card">
            <div class="row-between"><strong>Study streak</strong><RouterLink to="/progress" class="small">Details</RouterLink></div>
            <div class="row streak">
              <div><div class="big">{{ data.streak.current }}</div><span class="small muted">day{{ data.streak.current === 1 ? '' : 's' }} now</span></div>
              <div><div class="big muted-num">{{ data.streak.longest }}</div><span class="small muted">longest</span></div>
            </div>
            <div class="bar leaf"><span :style="{ width: Math.min(100, (100 * data.streak.today_minutes) / data.streak.goal_minutes) + '%' }" /></div>
            <p class="small muted">{{ streakMsg }}</p>
          </section>
        </div>

        <div class="grid main-grid">
          <div class="stack">
            <section class="card">
              <div class="card-title"><h3>Your rooms</h3><RouterLink to="/rooms" class="small">Discover rooms</RouterLink></div>
              <div v-if="!data.rooms.length" class="empty">
                <p>You're not in any rooms yet.</p>
                <RouterLink to="/rooms" class="btn sm">Find a room</RouterLink>
              </div>
              <div v-else class="list">
                <div v-for="r in data.rooms" :key="r.id" class="item room-row">
                  <div class="grow">
                    <RouterLink :to="`/rooms/${r.id}`" class="strong">{{ r.title }}</RouterLink>
                    <div class="small muted">
                      <template v-if="r.status === 'scheduled'">Starts {{ when(r.starts_at) }}</template>
                      <template v-else-if="r.status === 'studying'">Study phase · {{ hms(remaining(r.ends_at, now)) }} left</template>
                      <template v-else>Nest Race in progress</template>
                    </div>
                    <div v-if="r.status !== 'scheduled'" class="row small prog">
                      <div class="bar leaf grow"><span :style="{ width: r.progress.percent + '%' }" /></div>
                      <span class="nowrap">{{ r.progress.completed }}/{{ r.progress.total }} topics</span>
                    </div>
                  </div>
                  <span v-if="r.pomodoro.mode === 'focus'" class="chip leaf">Focusing</span>
                  <span v-else-if="r.pomodoro.mode === 'break'" class="chip warn">On a break</span>
                  <span v-else-if="r.status === 'race'" class="chip gold">Racing</span>
                  <RouterLink :to="`/rooms/${r.id}`" class="btn sm">{{ r.status === 'race' ? 'Race' : 'Open' }}</RouterLink>
                </div>
              </div>
            </section>

            <section v-if="data.halfway.length" class="card">
              <div class="card-title"><h3>Halfway quizzes</h3></div>
              <div class="list">
                <div v-for="h in data.halfway" :key="h.room_id" class="item">
                  <div class="grow"><strong>{{ h.title }}</strong>
                    <div class="small muted">
                      <template v-if="h.attempt?.submitted">Done: {{ h.attempt.score }}/{{ h.attempt.total }} correct, +{{ h.attempt.twigs }} twigs</template>
                      <template v-else-if="h.unlocked">Unlocked: you've finished half your topics</template>
                      <template v-else>Unlocks when you finish half the topics</template>
                    </div>
                  </div>
                  <RouterLink v-if="h.unlocked && !h.attempt?.submitted" :to="`/rooms/${h.room_id}?tab=quiz`" class="btn sm leaf">{{ h.attempt ? 'Continue' : 'Start' }}</RouterLink>
                </div>
              </div>
            </section>

            <section class="card">
              <div class="card-title"><h3>This week</h3><RouterLink to="/progress" class="small">All charts</RouterLink></div>
              <StateBlock :loading="week.loading.value" :error="week.error.value" :has-data="!!week.data.value" @retry="week.reload">
                <template v-if="week.data.value">
                  <p v-if="week.data.value.example" class="chip primary example-chip">Example data until your first focus session</p>
                  <p class="small muted">{{ week.data.value.totals.minutes }} focus minutes · {{ week.data.value.totals.completed_sessions }} completed sessions · {{ week.data.value.totals.topics }} topics ticked off</p>
                  <BarChart :rows="week.data.value.series.map((s) => ({ label: s.key, minutes: s.minutes }))" :series="[{ key: 'minutes', label: 'Focus minutes', color: 'var(--series-1)' }]"
                            :ref-line="{ value: week.data.value.goal_minutes, label: `Goal ${week.data.value.goal_minutes} min` }" :label-format="dayLabel" :format="(v) => `${Math.round(v)}`" :height="170" />
                </template>
              </StateBlock>
            </section>

            <section class="card">
              <div class="card-title"><h3>Study calendar</h3><span class="small muted">{{ data.streak.example ? 'Example · ' : '' }}Last 26 weeks</span></div>
              <Heatmap :days="data.streak.heatmap" :goal="data.streak.goal_minutes" />
            </section>

            <section class="card">
              <div class="card-title"><h3>Recent sessions</h3></div>
              <div v-if="!data.recent_sessions.length" class="empty small">Start a focus session in a room. Completed sessions show up here.</div>
              <table v-else class="table">
                <thead><tr><th>When</th><th>Subject</th><th class="num">Minutes</th><th>Status</th></tr></thead>
                <tbody>
                  <tr v-for="(s, i) in data.recent_sessions" :key="i">
                    <td>{{ ago(s.ended_at) }}</td><td>{{ s.subject }}</td><td class="num">{{ s.minutes }}</td>
                    <td><span class="chip" :class="s.status === 'completed' ? 'leaf' : 'warn'">{{ s.status === 'completed' ? 'Completed' : s.status === 'short' ? 'Too short to count' : 'Stopped early' }}</span></td>
                  </tr>
                </tbody>
              </table>
            </section>
          </div>

          <div class="stack">
            <section class="card">
              <div class="card-title"><h3>Upcoming meetings</h3><RouterLink to="/meetings" class="small">Schedule</RouterLink></div>
              <div v-if="!data.meetings.length" class="empty small">No meetings planned.</div>
              <div v-else class="list">
                <RouterLink v-for="m in data.meetings" :key="m.id" :to="`/meetings/${m.id}`" class="item link-item">
                  <Icon name="calendar" />
                  <div class="grow"><strong>{{ m.title }}</strong><div class="small muted">{{ when(m.starts_at) }}</div></div>
                  <span v-if="m.my_response === 'pending'" class="chip warn">Reply</span>
                </RouterLink>
              </div>
            </section>

            <section class="card">
              <div class="card-title"><h3>Notes &amp; AI</h3></div>
              <div v-if="data.pending_ai.length" class="notice info small">{{ data.pending_ai.length }} AI request{{ data.pending_ai.length > 1 ? 's' : '' }} processing…</div>
              <div v-if="!data.notes.length" class="empty small">Notes generated in your rooms appear here.</div>
              <div v-else class="list">
                <RouterLink v-for="n in data.notes" :key="n.id" :to="`/rooms/${n.room_id}?tab=notes&note=${n.id}`" class="item link-item">
                  <Icon name="file" />
                  <div class="grow"><strong>{{ n.title }}</strong><div class="small muted">{{ ago(n.created_at) }}</div></div>
                  <span class="chip" :class="n.status === 'shared' ? 'leaf' : ''">{{ n.status === 'shared' ? 'Shared' : 'Draft' }}</span>
                </RouterLink>
              </div>
            </section>

            <section class="card">
              <div class="card-title"><h3>Nest Race results</h3></div>
              <div v-if="!data.races.length && !data.recent_halfway.length" class="empty small">Finish a room to see your race results.</div>
              <div class="list">
                <div v-for="r in data.races" :key="r.race_id" class="item">
                  <span class="place" :class="{ gold: r.placement === 1 }">{{ r.placement || '–' }}</span>
                  <div class="grow"><strong>{{ r.room }}</strong><div class="small muted">{{ r.status === 'void' ? 'No valid race' : `${ord(r.placement)} of ${r.eligible_count}` }} · {{ r.twigs }} twigs · {{ r.accuracy }}% accuracy</div></div>
                </div>
                <div v-for="h in data.recent_halfway" :key="h.room_id + h.at" class="item">
                  <Icon name="check" />
                  <div class="grow"><strong>Halfway quiz: {{ h.title }}</strong><div class="small muted">{{ h.score }}/{{ h.total }} correct · +{{ h.twigs }} twigs</div></div>
                </div>
              </div>
            </section>

            <section class="card">
              <div class="card-title"><h3>Your flock online</h3><RouterLink to="/buddies?tab=now" class="small">See all</RouterLink></div>
              <div v-if="!online.data.value?.length" class="empty small">Nobody you follow is online right now.</div>
              <div v-else class="list">
                <div v-for="u in online.data.value.slice(0, 5)" :key="u.id" class="item">
                  <span class="presence"><Bird :bird="u.bird" :size="40" framed label="" /><span class="dot online-dot" /></span>
                  <div class="grow">
                    <RouterLink :to="`/u/${u.id}`" class="strong">{{ u.name }}</RouterLink>
                    <div v-if="u.activity.room" class="small muted">in <RouterLink :to="`/rooms/${u.activity.room.id}`">{{ u.activity.room.title }}</RouterLink></div>
                  </div>
                  <span class="chip" :class="ONLINE[u.activity.state]?.[0]">{{ ONLINE[u.activity.state]?.[1] || 'Online' }}</span>
                </div>
              </div>
            </section>

            <section class="card">
              <div class="card-title"><h3>Rooms for you</h3></div>
              <div v-if="!data.recommended_rooms.length" class="empty small">No open rooms match your subjects this week. <RouterLink to="/rooms/new">Start one!</RouterLink></div>
              <div class="stack">
                <RoomCard v-for="r in data.recommended_rooms" :key="r.id" :room="r" :busy="busy" class="flat" @join="join" />
              </div>
            </section>

            <section class="card">
              <div class="card-title"><h3>Study buddies for you</h3><RouterLink to="/buddies" class="small">More</RouterLink></div>
              <div v-if="!data.buddy_recommendations.length" class="empty small">No suggestions yet.</div>
              <div class="list">
                <div v-for="b in data.buddy_recommendations" :key="b.user_id" class="item">
                  <Bird :bird="b.bird" :size="40" framed label="" />
                  <div class="grow"><RouterLink :to="`/u/${b.user_id}`" class="strong">{{ b.name }}</RouterLink><div class="small muted">{{ b.score }}% match<template v-if="b.reasons[0]"> · {{ b.reasons[0] }}</template></div></div>
                  <button class="btn sm secondary" :disabled="busy" @click="follow(b)">Follow</button>
                </div>
              </div>
            </section>

            <section class="card cheer">
              <Bird :bird="data.user.bird" :size="64" mood="happy" label="" />
              <p><strong>Keep going!</strong><br /><span class="muted">You're doing great.</span></p>
            </section>
          </div>
        </div>
      </template>
    </StateBlock>
  </div>
</template>

<style scoped>
.top { margin-bottom: 16px; }
.nest-card, .golden { display: flex; gap: 14px; align-items: center; }
.grow { flex: 1; min-width: 0; }
.big { font-size: 2.2rem; font-weight: 800; line-height: 1.1; }
.muted-num { color: var(--muted); }
.streak { gap: 26px; margin: 4px 0 8px; }
.main-grid { grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); }
.strong { font-weight: 800; color: var(--ink); }
.prog { margin-top: 6px; flex-wrap: nowrap; }
.link-item { color: var(--ink); text-decoration: none; }
.link-item:hover { background: var(--surface-2); }
.place { width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center; background: var(--surface-3); font-weight: 800; flex: none; }
.place.gold { background: var(--gold-soft); color: var(--gold); }
.cheer { display: flex; align-items: center; gap: 12px; background: var(--primary-soft); border: 0; }
.cheer p { margin: 0; }
@media (max-width: 980px) { .main-grid { grid-template-columns: minmax(0, 1fr); } }
.example-chip { margin: 0 0 6px; }
.presence { position: relative; display: inline-flex; }
.online-dot { position: absolute; right: 0; bottom: 2px; width: 11px; height: 11px; background: var(--leaf); border: 2px solid var(--surface-solid); }
</style>
