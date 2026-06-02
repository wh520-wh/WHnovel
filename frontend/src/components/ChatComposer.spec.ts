import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import ChatComposer from './ChatComposer.vue'

describe('ChatComposer', () => {
  it('keeps the same textarea node when clicked', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        disabled: false,
        thinking: false,
        menuActive: false,
        showSpinner: false,
      },
    })

    const firstTextarea = wrapper.find('textarea').element

    await wrapper.find('textarea').trigger('click')
    await nextTick()

    expect(wrapper.find('textarea').element).toBe(firstTextarea)
  })

  it('only enables send for non-whitespace input and emits trimmed content', async () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '   ',
        disabled: false,
        thinking: false,
        menuActive: false,
        showSpinner: false,
      },
    })

    expect(wrapper.find('.send-btn').attributes('disabled')).toBeDefined()

    await wrapper.setProps({ modelValue: '  我自己决定行动  ' })

    expect(wrapper.find('.send-btn').attributes('disabled')).toBeUndefined()

    await wrapper.find('.send-btn').trigger('click')

    expect(wrapper.emitted('send')).toEqual([['我自己决定行动']])
  })

  it('keeps the character count inside an input shell that reserves text space', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        disabled: false,
        thinking: false,
        menuActive: false,
        showSpinner: false,
      },
    })

    expect(wrapper.find('.input-shell').exists()).toBe(true)
    expect(wrapper.find('.input-shell .bottom-input').exists()).toBe(true)
    expect(wrapper.find('.input-shell .char-count').exists()).toBe(true)
  })

  it('does not emit resized again when the composer height stays unchanged', async () => {
    const modelValue = ref('')
    const Host = defineComponent({
      components: { ChatComposer },
      setup() {
        return { modelValue }
      },
      template: `
        <ChatComposer
          v-model="modelValue"
          :disabled="false"
          :thinking="false"
          :menuActive="false"
          :showSpinner="false"
        />
      `,
    })

    const wrapper = mount(Host)
    const composer = wrapper.findComponent(ChatComposer)
    const root = composer.find('.input-area').element as HTMLDivElement
    const textarea = composer.find('textarea').element as HTMLTextAreaElement

    Object.defineProperty(root, 'offsetHeight', {
      configurable: true,
      get: () => 48,
    })
    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      get: () => 48,
    })

    const resizeEventCount = composer.emitted('resized')?.length ?? 0

    modelValue.value = '保持单行'
    await nextTick()
    await nextTick()

    expect(composer.emitted('resized')?.length ?? 0).toBe(resizeEventCount)
  })

  it('shows body streaming hint while AI text is streaming', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        disabled: false,
        thinking: true,
        awaitingTail: false,
        menuActive: false,
        showSpinner: true,
      },
    })

    expect(wrapper.find('.ai-thinking-hint').text()).toContain('AI 正在回复')
  })

  it('shows tail waiting hint after body text ends', () => {
    const wrapper = mount(ChatComposer, {
      props: {
        modelValue: '',
        disabled: false,
        thinking: false,
        awaitingTail: true,
        menuActive: false,
        showSpinner: true,
      },
    })

    expect(wrapper.find('.ai-thinking-hint').text()).toContain('正在整理状态和选项')
  })
})
