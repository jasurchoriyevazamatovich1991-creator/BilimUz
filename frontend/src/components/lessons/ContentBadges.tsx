/**
 * Small presentational indicators for which content fields a Lesson
 * has (approved decision 1) — only rendered for fields that are
 * actually present, no icon library (plain text pills, same visual
 * shape as components/users/StatusBadge.tsx's rounded pill style, a
 * distinct neutral color scheme since these aren't status values).
 */
interface ContentBadgesProps {
  video: string | null;
  pdf: string | null;
  content: string | null;
}

export function ContentBadges({ video, pdf, content }: ContentBadgesProps) {
  const badges: string[] = [];
  if (video) badges.push("Video");
  if (pdf) badges.push("PDF");
  if (content) badges.push("Text");

  if (badges.length === 0) {
    return <span className="text-foreground/40">—</span>;
  }

  return (
    <span className="flex flex-wrap gap-1">
      {badges.map((label) => (
        <span key={label} className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
          {label}
        </span>
      ))}
    </span>
  );
}
