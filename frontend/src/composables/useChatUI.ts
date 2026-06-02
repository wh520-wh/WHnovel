import { ref } from 'vue'

export function useChatUI() {
  const sending = ref(false)
  const streaming = ref(false)
  const awaitingTail = ref(false)
  const generatingStateBroadcast = ref(false)
  const recallInProgress = ref(false)
  const streamingFollow = ref(true)
  const loading = ref(false)

  function setStreamingFollow(enabled: boolean) {
    streamingFollow.value = enabled
  }

  return {
    sending,
    streaming,
    awaitingTail,
    generatingStateBroadcast,
    recallInProgress,
    streamingFollow,
    loading,
    setStreamingFollow,
  }
}
