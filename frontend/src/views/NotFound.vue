<template>
  <div class="not-found">
    <h2>404</h2>
    <p>页面不存在</p>
    <el-button @click="$router.push('/')">返回首页</el-button>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  min-height: 60dvh;
  gap: 12px;
  color: var(--color-text-secondary);
}
</style>
