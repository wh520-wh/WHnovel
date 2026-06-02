<!-- Props: lines?, lastLineWidth? -->
<template>
  <div class="skeleton-text">
    <div
      v-for="i in lines"
      :key="i"
      class="skeleton-line"
      :style="{ width: i === lines ? lastLineWidth : '100%' }"
    />
  </div>
</template>
<script setup lang="ts">
withDefaults(defineProps<{
  lines?: number
  lastLineWidth?: string
}>(), {
  lines: 3,
  lastLineWidth: '60%',
})
</script>
<style scoped>
.skeleton-text {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.skeleton-line {
  height: 12px;
  background: var(--skeleton-base);
  border-radius: var(--skeleton-radius);
}
</style>
