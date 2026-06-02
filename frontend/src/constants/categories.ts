/** 故事分类常量，全局共享 */
export const STORY_CATEGORIES = ['恋爱', '冒险', '悬疑', '科幻', '其他'] as const
export type StoryCategory = (typeof STORY_CATEGORIES)[number]
