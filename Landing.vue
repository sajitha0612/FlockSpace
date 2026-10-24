<script setup>
import Bird from '../components/Bird.vue'
import Logo from '../components/Logo.vue'
import Nest from '../components/Nest.vue'

const steps = [
  ['Discover or create a room', 'Pick a subject, topics, schedule, duration and size.'],
  ['Study together', 'Your own Pomodoro rhythm, shared chat, notes and AI help.'],
  ['Unlock the halfway quiz', 'Tick off half your topics to test yourself.'],
  ['Race to build your nest', 'A common final quiz: every right answer is a twig.'],
  ['Earn Golden Nests', 'Win races, unlock milestones and dress up your bird.'],
]
</script>

<template>
  <div class="landing">
    <header class="topbar glass">
      <span class="logo"><Logo :size="38" /></span>
      <div class="spacer" />
      <RouterLink to="/login" class="btn ghost">Sign in</RouterLink>
      <RouterLink to="/signup" class="btn">Get started</RouterLink>
    </header>
    <section class="hero">
      <div class="copy glass">
        <h1>Find your flock.<br />Study together.<br />Build your nest.</h1>
        <p class="lead">Join study rooms, meet like-minded buddies, track your progress and grow — together.</p>
        <div class="row">
          <RouterLink to="/signup" class="btn lg">Get started</RouterLink>
          <RouterLink to="/login" class="btn ghost lg">I already have an account</RouterLink>
        </div>
      </div>
      <div class="art" aria-hidden="true">
        <div class="leaf l1" /><div class="leaf l2" /><div class="leaf l3" />
        <div class="perch"><Bird :size="170" mood="idle" label="" /></div>
        <Nest :progress="100" :size="260" label="" />
      </div>
    </section>
    <section class="steps">
      <div v-for="(s, i) in steps" :key="s[0]" class="step card">
        <span class="num">{{ i + 1 }}</span>
        <h3>{{ s[0] }}</h3>
        <p class="muted small">{{ s[1] }}</p>
      </div>
    </section>
    <footer class="small foot"><span class="glass foot-pill">Rewards come only from quizzes, never from time online. AI helps you learn; it never decides who wins.</span></footer>
  </div>
</template>

<style scoped>
.landing { min-height: 100vh; padding-top: 14px; }
.copy { border-radius: 24px; padding: 32px; box-shadow: var(--shadow-lg); }
.foot-pill { display: inline-block; border-radius: 999px; padding: 8px 18px; color: var(--ink-2); }
.topbar { display: flex; align-items: center; gap: 8px; padding: 12px 22px; max-width: 1140px; margin: 0 auto; border-radius: 999px; box-shadow: var(--shadow); }
.logo { font-size: 1.7rem; }
.hero { max-width: 1180px; margin: 0 auto; padding: 40px 28px 20px; display: grid; grid-template-columns: 1.1fr 1fr; gap: 32px; align-items: center; }
h1 { font-size: clamp(2.2rem, 5vw, 3.6rem); line-height: 1.08; }
.lead { font-size: 1.15rem; color: var(--ink-2); max-width: 30ch; margin: 18px 0 24px; }
.art { position: relative; display: flex; flex-direction: column; align-items: center; }
.perch { margin-bottom: -70px; z-index: 1; }
.leaf { position: absolute; width: 46px; height: 22px; border-radius: 0 100% 0 100%; background: var(--leaf); opacity: .8; }
.l1 { top: 4%; left: 12%; transform: rotate(-25deg); }
.l2 { top: 30%; right: 6%; transform: rotate(30deg); background: #8bbf6a; }
.l3 { bottom: 10%; left: 4%; transform: rotate(10deg); background: #a9cf7f; }
.steps { max-width: 1180px; margin: 30px auto 0; padding: 0 28px; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }
.num { display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; background: var(--primary-soft); color: var(--primary); font-weight: 800; margin-bottom: 8px; }
.step h3 { font-size: 1rem; }
.foot { text-align: center; padding: 36px 16px; }
@media (max-width: 900px) { .hero { grid-template-columns: 1fr; text-align: center; } .lead { margin-inline: auto; } .hero .row { justify-content: center; } .steps { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .steps { grid-template-columns: 1fr; } .topbar { padding: 10px 14px; margin: 0 12px; } .copy { padding: 22px; } .hero { padding: 20px 16px; } .steps { padding: 0 16px; } }
</style>
