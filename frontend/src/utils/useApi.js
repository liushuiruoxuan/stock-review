import { ref } from 'vue'

export function useApi(fn) {
  const data = ref(null)
  const loading = ref(true)
  const error = ref('')
  function run() {
    loading.value = true
    return fn()
      .then((d) => {
        data.value = d
      })
      .catch((e) => {
        error.value = String(e)
      })
      .finally(() => {
        loading.value = false
      })
  }
  return { data, loading, error, run }
}
