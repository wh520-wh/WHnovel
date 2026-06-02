<!-- Props: size?, shape? ('circle'|'square') -->
<template>
  <div
    class="skeleton-avatar"
    :class="{ circle: shape === 'circle', square: shape !== 'circle' }"
    :style="{ width: size, height: size }"
  />
</template>
<script setup lang="ts">
withDefaults(defineProps<{
  size?: string
  shape?: 'circle' | 'square'
}>(), {
  size: '40px',
  shape: 'circle',
})
</script>
<style scoped>
.skeleton-avatar {
  background: var(--skeleton-base);
  flex-shrink: 0;
}
.skeleton-avatar.circle {
  border-radius: 50%;
}
.skeleton-avatar.square {
  border-radius: var(--skeleton-radius);
}
</style>
