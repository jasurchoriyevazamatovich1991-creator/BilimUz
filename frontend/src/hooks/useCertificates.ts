/**
 * Certificate data hooks — same shape as hooks/useResults.ts (Sprint
 * 20) / hooks/useTests.ts (Sprint 19). `useIssueCertificate` handles
 * the idempotent-creation flow: a second call for an already-certified
 * passing result returns the SAME certificate (200-shaped success, not
 * an error) — the mutation's onSuccess treats this identically to a
 * fresh issue, since the backend itself makes no distinction.
 */
import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import { certificatesApi, type IssueCertificateRequest } from "@/api/certificates";
import { useToastStore } from "@/store/toastStore";
import { ApiError } from "@/api/client";

function useToastOnQueryError(query: UseQueryResult<unknown, unknown>) {
  const addToast = useToastStore((s) => s.addToast);
  useEffect(() => {
    if (query.isError) {
      addToast(query.error instanceof ApiError ? query.error.message : "Ma'lumot yuklanmadi");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.isError, query.error]);
}

export function useMyCertificates(params: { page: number; per_page: number }) {
  const query = useQuery({ queryKey: ["certificates", "list", params], queryFn: () => certificatesApi.listMine(params) });
  useToastOnQueryError(query);
  return query;
}

export function useCertificate(certificateId: string | undefined) {
  const query = useQuery({
    queryKey: ["certificates", "detail", certificateId],
    queryFn: () => certificatesApi.get(certificateId as string),
    enabled: !!certificateId,
  });
  useToastOnQueryError(query);
  return query;
}

export function useIssueCertificate() {
  const queryClient = useQueryClient();
  const addToast = useToastStore((s) => s.addToast);

  return useMutation({
    mutationFn: (data: IssueCertificateRequest) => certificatesApi.issue(data),
    onSuccess: (certificate) => {
      queryClient.invalidateQueries({ queryKey: ["certificates", "list"] });
      queryClient.setQueryData(["certificates", "detail", certificate.id], certificate);
      addToast("Sertifikat tayyor", "success");
    },
    onError: (error) =>
      addToast(
        // A 422 here specifically means "this result isn't a passing
        // one" (CannotCertifyFailedResultException) — the message the
        // backend returns already says this in Uzbek, surfaced as-is
        // rather than a second, invented generic message.
        error instanceof ApiError ? error.message : "Sertifikat berib bo'lmadi",
      ),
  });
}

/** Public — no auth required, used by VerifyCertificatePage.tsx. */
export function useVerifyCertificate() {
  return useMutation({
    mutationFn: (code: string) => certificatesApi.verify(code),
  });
}
