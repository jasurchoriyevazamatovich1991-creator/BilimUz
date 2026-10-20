/**
 * Task 1 (IELTS/SAT/GRE audit) — renders question/option media during
 * an exam attempt.
 *
 * The attempt payload carries only {id, media_type, option_id}; each
 * item asks GET /attempts/{attemptId}/media/{mediaId}/view-url for a
 * short-lived URL (the backend re-checks ownership, attempt activity
 * and delivery scope on every call). The URL lives in React Query cache
 * only — never persisted.
 *
 * Refetch policy is deliberate: a background refetch would swap `src`
 * and restart a playing audio/video, so window-focus/reconnect refetches
 * are off. The cached URL is treated as fresh for 4 minutes (backend
 * TTL is 5); a remount after that fetches a new one. If the browser
 * fails to load the file (e.g. an expired URL), the item shows an
 * error with a retry button that fetches a fresh URL.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { attemptsApi } from "@/api/attempts";

/** Task 3 — which endpoint signs this media: question/option media or
 * question-group media. Also part of the cache key, so the two id
 * spaces can never collide. */
export type AttemptMediaSource = "question" | "group";

/** The fields this component needs; satisfied by both AttemptMediaOut
 * and AttemptGroupMediaOut. */
export interface AttemptMediaItemData {
  id: string;
  media_type: string;
}

const VIEW_URL_FRESH_MS = 4 * 60 * 1000;

const TYPE_LABEL: Record<string, string> = {
  image: "rasm",
  audio: "audio",
  video: "video",
  formula: "formula",
};

interface AttemptMediaItemProps {
  attemptId: string;
  media: AttemptMediaItemData;
  source: AttemptMediaSource;
  /** Accessible name, e.g. "Savol audiosi 1". */
  label: string;
}

function AttemptMediaItem({ attemptId, media, source, label }: AttemptMediaItemProps) {
  const [loadFailed, setLoadFailed] = useState(false);
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["attempts", attemptId, source === "group" ? "group-media" : "media", media.id, "view-url"],
    queryFn: () =>
      source === "group" ? attemptsApi.getGroupMediaViewUrl(attemptId, media.id) : attemptsApi.getMediaViewUrl(attemptId, media.id),
    staleTime: VIEW_URL_FRESH_MS,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: 1,
  });

  function handleRetry() {
    setLoadFailed(false);
    void refetch();
  }

  if (isLoading) {
    return (
      <div role="status" className="rounded-md bg-muted px-3 py-2 text-sm text-foreground/50">
        {label} yuklanmoqda...
      </div>
    );
  }

  if (isError || !data || loadFailed) {
    return (
      <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
        <span>{label} yuklanmadi.</span>
        <button
          type="button"
          onClick={handleRetry}
          disabled={isFetching}
          className="rounded-md border border-destructive/40 px-2 py-1 text-xs disabled:opacity-50"
        >
          Qayta urinish
        </button>
      </div>
    );
  }

  const src = data.view_url;
  switch (media.media_type) {
    case "image":
    case "formula":
      return (
        <img
          src={src}
          alt={label}
          loading="lazy"
          onError={() => setLoadFailed(true)}
          className="max-h-96 max-w-full rounded-md border border-border object-contain"
        />
      );
    case "audio":
      return (
        <audio
          controls
          preload="metadata"
          src={src}
          aria-label={label}
          onError={() => setLoadFailed(true)}
          className="w-full"
        >
          Brauzeringiz audio pleyerni qo'llab-quvvatlamaydi.
        </audio>
      );
    case "video":
      return (
        <video
          controls
          preload="metadata"
          src={src}
          aria-label={label}
          onError={() => setLoadFailed(true)}
          className="max-h-96 w-full rounded-md bg-black"
        >
          Brauzeringiz video pleyerni qo'llab-quvvatlamaydi.
        </video>
      );
    default:
      return <p className="text-sm text-foreground/50">{label}: qo'llab-quvvatlanmaydigan media turi.</p>;
  }
}

interface AttemptMediaListProps {
  attemptId: string;
  media: AttemptMediaItemData[];
  /** "Savol" for question-level media, "Variant" for option-level,
   * "Bo'lim" for question-group media. */
  owner: string;
  /** Defaults to "question" (Task 1 behavior). */
  source?: AttemptMediaSource;
  testId?: string;
}

/** Renders nothing for an empty list, so questions without media look
 * exactly as they did before Task 1. */
export function AttemptMediaList({ attemptId, media, owner, source = "question", testId = "attempt-media" }: AttemptMediaListProps) {
  if (media.length === 0) return null;
  return (
    <div className="mb-4 space-y-3" data-testid={testId}>
      {media.map((m, i) => (
        <AttemptMediaItem
          key={m.id}
          attemptId={attemptId}
          media={m}
          source={source}
          label={`${owner} ${TYPE_LABEL[m.media_type] ?? "media"}${media.length > 1 ? ` ${i + 1}` : ""}`}
        />
      ))}
    </div>
  );
}
