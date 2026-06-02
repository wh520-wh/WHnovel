import {
  sanitizeAiDisplayText,
  sanitizeAiInlineText,
  sanitizeAiStringList,
  collapseBlankLines,
} from './aiText'

export const OPTION_BLOCK_CUE_RE =
  /(?:你必须立刻行动|你必须行动|你需要立刻行动|你需要马上行动|接下来你|接下来该|下一步|请选择|你的选择|你可以选择|该怎么做|如何行动)/i

export const OPTION_LINE_RE =
  /^(?:[-*]\s*|(?:\d+|[一二三四五六七八九十])[\.\、\)]\s*|(?:立刻|立即|迅速|尝试|低声|直接|先|继续|转身|上前|后退|躲开|躲入|躲到|绕到|冲向|搜索|寻找|调查|检查|观察|回应|追问|询问|触碰|触摸|翻找|读取|拿起|握紧|使用|施展|呼唤|伪装|潜入|靠近|远离|稳定|压低|逃离|扭曲|索取))/

export function stripTrailingOptionBlock(text: string): string {
  const normalized = String(text || '').replace(/\r\n?/g, '\n').trim()
  if (!normalized) return ''

  const lines = normalized.split('\n')
  let end = lines.length - 1
  while (end >= 0 && !lines[end].trim()) end -= 1
  if (end < 1) return normalized

  let start = end
  while (start >= 0 && lines[start].trim()) start -= 1

  const blockLines = lines.slice(start + 1, end + 1).map((line) => line.trim()).filter(Boolean)
  if (blockLines.length < 2 || blockLines.length > 5) return normalized
  if (blockLines.some((line) => line.length < 6 || line.length > 40)) return normalized
  if (blockLines.some((line) => /[`{}\[\]"]/.test(line) || /[。！？!?；;：:]$/.test(line) || /^[（(“"「]/.test(line))) {
    return normalized
  }
  if (blockLines.some((line) => !OPTION_LINE_RE.test(line))) return normalized

  let prevNonEmpty = ''
  for (let index = start; index >= 0; index -= 1) {
    if (lines[index].trim()) {
      prevNonEmpty = lines[index].trim()
      break
    }
  }

  const hasCue = !!prevNonEmpty && OPTION_BLOCK_CUE_RE.test(prevNonEmpty)
  const hasBlankSeparator = start >= 0 && !lines[start].trim()
  if (!hasCue && !(hasBlankSeparator && blockLines.length >= 3)) return normalized

  return collapseBlankLines(lines.slice(0, start + 1).join('\n'))
}

export function normalizeOptions(options: string[] | null | undefined): string[] {
  return sanitizeAiStringList(options)
}

export function normalizePlotLabel(label: string | null | undefined): string | null {
  return sanitizeAiInlineText(label) || null
}

export { sanitizeAiDisplayText, sanitizeAiInlineText, sanitizeAiStringList }
