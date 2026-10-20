/**
 * Task 3 — attach/remove audio (or images) on a question group, e.g. the
 * recording for an IELTS Listening section that all of the group's
 * questions share. Reuses the existing FileUploader (no new upload path):
 * the finished upload's id is attached with POST
 * /tests/question-groups/{id}/media, and the backend decides media_type
 * from the upload itself (audio/image only).
 */
import { FileUploader } from "@/components/uploads/FileUploader";
import type { QuestionGroupOut } from "@/api/examConfig";
import { useAddQuestionGroupMedia, useRemoveQuestionGroupMedia } from "@/hooks/useExamConfig";

const TYPE_LABEL: Record<string, string> = { audio: "Audio", image: "Rasm" };

interface GroupMediaManagerProps {
  testId: string;
  group: QuestionGroupOut;
}

export function GroupMediaManager({ testId, group }: GroupMediaManagerProps) {
  const addMedia = useAddQuestionGroupMedia(testId);
  const removeMedia = useRemoveQuestionGroupMedia(testId);
  const media = group.media ?? [];

  return (
    <div className="mt-3 space-y-2" data-testid={`group-media-manager-${group.id}`}>
      <p className="text-xs font-medium text-foreground/70">Guruh mediasi (masalan, Listening audiosi)</p>
      {media.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {media.map((m, i) => (
            <li key={m.id} className="rounded bg-primary/10 px-2 py-1 text-xs text-primary">
              {TYPE_LABEL[m.media_type] ?? m.media_type} {i + 1}
              <button
                type="button"
                onClick={() => removeMedia.mutate({ groupId: group.id, mediaId: m.id })}
                disabled={removeMedia.isPending}
                aria-label={`${TYPE_LABEL[m.media_type] ?? "Media"} ${i + 1} ni guruhdan olib tashlash`}
                className="ml-2 text-destructive disabled:opacity-50"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-foreground/50">Media biriktirilmagan.</p>
      )}
      <FileUploader
        disabled={addMedia.isPending}
        onSuccess={(uploadId) => addMedia.mutate({ groupId: group.id, uploadId })}
      />
    </div>
  );
}
