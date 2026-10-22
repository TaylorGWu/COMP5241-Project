/** A chapter's editor is always addressed within its owning course. */
export function chapterHref(courseId: string, chapterId: string): string {
  return `/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}`;
}

function chapterApiPath(courseId: string, chapterId: string): string {
  return `/api/demo/courses/${encodeURIComponent(courseId)}/chapters/${encodeURIComponent(chapterId)}`;
}

export function chapterDiagramPath(courseId: string, chapterId: string, assetId: string): string {
  return `${chapterApiPath(courseId, chapterId)}/assets/${encodeURIComponent(assetId)}.svg`;
}

export function chapterDeckPath(courseId: string, chapterId: string): string {
  return `${chapterApiPath(courseId, chapterId)}/export/deck.pptx`;
}

export function chapterToolPath(courseId: string, chapterId: string, tool: string): string {
  const cleanTool = tool.split("/").map(encodeURIComponent).join("/");
  return `${chapterApiPath(courseId, chapterId)}/${cleanTool}`;
}
