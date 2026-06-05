const STRUCTURED_FIELD_RE =
  /"(?:reply_text|scene|options|character_state|story_state|memory_update|plot_label|highlight_terms|content|openings|title|category|tags|cover_url|description|world_setting|image_style)"/i

const STRUCTURED_LINE_RE =
  /^\s*"?(?:reply_text|scene|options|character_state|story_state|memory_update|plot_label|highlight_terms|content|openings|title|category|tags|cover_url|description|world_setting|image_style)"?\s*:/

const META_LINE_PATTERNS = [
  /^(?:系统提示|系统说明|输出格式|response_format|json schema)\b/i,
  /^(?:以下是输出|以下为输出|以下内容为|仅返回json|只返回json)/i,
  /^(?:用户输入|参考设定|根据设定|根据要求)[:：]/,
]

export function collapseBlankLines(text: string): string {
  return text.replace(/\n{3,}/g, '\n\n').trim()
}

function looksLikeStructuredJson(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return false
  if (!/^[[{]/.test(trimmed) || !/[}\]]$/.test(trimmed)) return false
  if (STRUCTURED_FIELD_RE.test(trimmed)) return true

  try {
    const parsed = JSON.parse(trimmed)
    return typeof parsed === 'object' && parsed !== null
  } catch {
    return false
  }
}

export function sanitizeAiDisplayText(input: string | null | undefined): string {
  let text = String(input || '')
    .replace(/\r\n?/g, '\n')
    .trim()
  if (!text) return ''

  text = text.replace(/```[\s\S]*?```/g, '').trim()
  if (!text) return ''
  if (looksLikeStructuredJson(text)) return ''

  const cleanedLines = text
    .split('\n')
    .map((line) => line.trimEnd())
    .filter((line) => {
      const trimmed = line.trim()
      if (!trimmed) return true
      if (/^[[\]{},]+$/.test(trimmed)) return false
      if (STRUCTURED_LINE_RE.test(trimmed)) return false
      return !META_LINE_PATTERNS.some((pattern) => pattern.test(trimmed))
    })
    .join('\n')

  const cleaned = collapseBlankLines(cleanedLines)
  if (!cleaned) return ''
  if (looksLikeStructuredJson(cleaned)) return ''
  return cleaned
}

export function sanitizeAiInlineText(input: string | null | undefined): string {
  return sanitizeAiDisplayText(input).replace(/\s+/g, ' ').trim()
}

export function sanitizeAiStringList(
  items: Array<string | null | undefined> | null | undefined,
): string[] {
  const result: string[] = []
  const seen = new Set<string>()

  for (const raw of items || []) {
    const value = sanitizeAiInlineText(raw)
    if (!value || seen.has(value)) continue
    seen.add(value)
    result.push(value)
  }

  return result
}
