<!-- Props: width?, height?, borderRadius? -->
<template>
  <div
    class="skeleton-block"
    :style="{
      width: width || '100%',
      height: height || '16px',
      borderRadius: borderRadius || '8px',
    }"
  />
</template>
<script setup lang="ts">
withDefaults(
  defineProps<{
    width?: string
    height?: string
    borderRadius?: string
  }>(),
  {
    width: '100%',
    height: '16px',
    borderRadius: '8px',
  },
)
</script>
<style scoped>
.skeleton-block {
  background: var(--skeleton-base);
}
</style>
