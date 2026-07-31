/** 故事笔记本条目 */
export interface NotebookEntry {
  text: string
  status: 'active' | 'closed'
}

/** 故事笔记本：三线（世界线/人物线/感情线），与后端 Archive.notebook 结构一致 */
export interface StoryNotebook {
  world_line: NotebookEntry[]
  character_line: NotebookEntry[]
  relationship_line: NotebookEntry[]
}
