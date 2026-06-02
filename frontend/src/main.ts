import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css'
import {
  ChatDotRound,
  Cpu,
  DataAnalysis,
  Fold,
  House,
  Refresh,
  Search,
  Setting,
} from '@element-plus/icons-vue'
import './styles/global.css'
import App from './App.vue'
import router from './router'
import { ElMessage } from 'element-plus'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 注册实际使用的图标（仅按需，避免 ~290 个图标全量打入 bundle）
app.component('ChatDotRound', ChatDotRound)
app.component('Cpu', Cpu)
app.component('DataAnalysis', DataAnalysis)
app.component('Fold', Fold)
app.component('House', House)
app.component('Refresh', Refresh)
app.component('Search', Search)
app.component('Setting', Setting)

// 全局错误边界
app.config.errorHandler = (err, _instance, info) => {
  console.error('Global error:', err, info)
  ElMessage.error('发生了未知错误，请刷新页面')
}

// 捕获未处理的 Promise 拒绝
window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason)
})

app.mount('#app')
