<script setup>
import Bird from '../components/Bird.vue'
</script>

<template>
  <div class="nf">
    <Bird :size="120" mood="sad" label="" />
    <h1>This branch is empty</h1>
    <p class="muted">The page you're looking for flew away.</p>
    <RouterLink to="/" class="btn">Back home</RouterLink>
  </div>
</template>

<style scoped>
.nf { min-height: 70vh; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: 8px; padding: 24px; }
</style>
