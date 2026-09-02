/**
 * NEW component (approved decision 5) — deliberately NOT a modification
 * of components/lessons/ContentBadges.tsx (Sprint 18, protected,
 * unchanged). Question Media has a different, larger type set
 * (image/audio/video/formula, verified against
 * backend/app/modules/questions/constants.py's ALLOWED_MEDIA_TYPES)
 * than Lessons' fixed three — reusing ContentBadges as-is would have
 * hardcoded the wrong labels. Same visual pill shape, independent code.
 */
interface MediaTypeBadgesProps {
  mediaTypes: string[];
}

const LABELS: Record<string, string> = {
  image: "Rasm",
  audio: "Audio",
  video: "Video",
  formula: "Formula",
};

export function MediaTypeBadges({ mediaTypes }: MediaTypeBadgesProps) {
  const uniqueTypes = Array.from(new Set(mediaTypes));

  if (uniqueTypes.length === 0) {
    return <span className="text-foreground/40">—</span>;
  }

  return (
    <span className="flex flex-wrap gap-1">
      {uniqueTypes.map((type) => (
        <span key={type} className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
          {LABELS[type] ?? type}
        </span>
      ))}
    </span>
  );
}
