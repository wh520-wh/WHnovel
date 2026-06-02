let container: HTMLElement | null = null
let counter = 0

function ensureContainer(): HTMLElement {
  if (container) return container
  container = document.createElement('div')
  container.id = 'global-toast-container'
  Object.assign(container.style, {
    position: 'fixed',
    bottom: '80px',
    left: '50%',
    transform: 'translateX(-50%)',
    zIndex: '9999',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '8px',
    pointerEvents: 'none',
  })
  document.body.appendChild(container)
  return container
}

export function showToast(message: string): void {
  const c = ensureContainer()
  ++counter
  const el = document.createElement('div')
  el.className = 'global-toast'
  el.textContent = message
  el.style.cssText = [
    'padding: 10px 24px',
    'border-radius: 12px',
    'background: rgba(20, 184, 166, 0.92)',
    'color: #fff',
    'font-size: 13px',
    'font-family: inherit',
    'font-weight: 500',
    'pointer-events: none',
    'opacity: 0',
    'transform: translateY(8px)',
    'transition: opacity 200ms ease-out, transform 200ms ease-out',
    `z-index: ${9999 + counter}`,
    'box-shadow: 0 4px 20px rgba(20, 184, 166, 0.35)',
  ].join(';')

  c.appendChild(el)

  // Force reflow before starting entry animation
  void el.offsetHeight
  el.style.opacity = '1'
  el.style.transform = 'translateY(0)'

  setTimeout(() => {
    el.style.opacity = '0'
    el.style.transform = 'translateY(-8px)'
    el.addEventListener('transitionend', () => {
      el.remove()
    }, { once: true })
  }, 2000)
}
