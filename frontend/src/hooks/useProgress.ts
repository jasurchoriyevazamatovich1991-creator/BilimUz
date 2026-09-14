/**
 * New file — Sprint 36. Follows the exact same hook shape as every
 * other module (e.g. useCertificates.ts/useResults.ts): a plain
 * useQuery for reads, useMutation + cache invalidation for writes.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { progressApi } from "@/api/progress";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

export function useMyProgress() {
  const query = useQuery({
    queryKey: ["progress", "me"],
    queryFn: () => progressApi.getMyProgress(),
  });
  return query;
}

export function useCompleteLesson() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (lessonId: string) => progressApi.completeLesson(lessonId),
    onSuccess: () => {
      // Only the progress query needs invalidating — the lesson itself
      // (content/video/pdf) never changes as a result of completion,
      // so re-fetching it would be an unnecessary request.
      queryClient.invalidateQueries({ queryKey: ["progress", "me"] });
      addToast("Dars tugatilgan deb belgilandi", "success");
    },
    onError: (error) => addToast(error instanceof ApiError ? error.message : "Xatolik yuz berdi"),
  });
}
