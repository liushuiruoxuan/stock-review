import { ref } from 'vue'

const MOBILE_BREAKPOINT = 768

// 全局单例，让所有组件共享同一个响应式状态，避免每个组件各自挂载 resize 监听。
const isMobile = ref(typeof window !== 'undefined' && window.innerWidth <= MOBILE_BREAKPOINT)

if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    isMobile.value = window.innerWidth <= MOBILE_BREAKPOINT
  })
}

export function useResponsive() {
  return { isMobile, breakpoint: MOBILE_BREAKPOINT }
}
