/**
 * useStorageSync — 跨 Tab 状态同步
 *
 * 原理：同一个浏览器 session 中，localStorage 的变化会触发所有同源 Tab 的 `storage` 事件。
 * 通过在修改状态后写入标记，其他 Tab 检测到标记变化时重新拉取最新数据。
 *
 * 使用方式：
 *   const sync = useStorageSync()
 *   // 在 store 的 mutation 完成后：
 *   sync.broadcast('settings')
 *   // 在 store 初始化时注册回调（可多次调用，自动去重）：
 *   sync.watch('settings', () => settingsStore.fetchSettings())
 *   // 需要清理时：
 *   const unwatch = sync.watch('settings', fn)
 *   unwatch()
 */

const PREFIX = '__sync:'
const listeners = new Map<string, Set<() => void>>()
const handlers = new Map<string, (e: StorageEvent) => void>()

function broadcast(channel: string) {
  localStorage.setItem(PREFIX + channel, String(Date.now()))
}

function watch(channel: string, fn: () => void): () => void {
  if (!listeners.has(channel)) {
    listeners.set(channel, new Set())
    const handler = (e: StorageEvent) => {
      if (e.key === PREFIX + channel) {
        listeners.get(channel)?.forEach(cb => cb())
      }
    }
    handlers.set(channel, handler)
    window.addEventListener('storage', handler)
  }

  listeners.get(channel)!.add(fn)

  // 返回取消订阅函数
  return () => {
    listeners.get(channel)?.delete(fn)
  }
}

export function useStorageSync() {
  return { broadcast, watch }
}
