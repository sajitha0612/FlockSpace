<script setup>
// The FlockSpace mark: the house sparrow on its nest (same drawing as the favicon) plus the two-tone wordmark.
defineProps({ size: { type: Number, default: 30 } })
</script>

<template>
  <span class="logo-mark">
    <svg :width="size" :height="size" viewBox="0 0 64 64" aria-hidden="true">
      <ellipse cx="32" cy="46" rx="24" ry="10" fill="#b07a3c" />
      <ellipse cx="32" cy="30" rx="16" ry="14" fill="#8a5a3b" />
      <ellipse cx="34" cy="34" rx="10" ry="9" fill="#f3e6d3" />
      <circle cx="38" cy="25" r="2.6" fill="#1b2a4e" />
      <path d="M46 27l7 2-7 3z" fill="#e0703c" />
    </svg>
    <span class="word">Flock<span>Space</span></span>
  </span>
</template>

<style scoped>
.logo-mark { display: inline-flex; align-items: center; gap: 8px; }
.word { font-weight: 800; color: var(--twig); letter-spacing: -.01em; }
.word span { color: var(--primary); }
</style>
