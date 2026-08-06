/**
 * New hook (approved decision — NOT an extension of utils/roleConfig.ts,
 * which maps role NAME -> panel and is unrelated to this id -> role
 * lookup). Wraps GET /roles via TanStack Query, cached — roles change
 * rarely, a long staleTime avoids refetching on every Users page visit.
 */
import { useQuery } from "@tanstack/react-query";
import { rolesApi } from "@/api/roles";

export function useRoles() {
  return useQuery({
    queryKey: ["roles", "list"],
    queryFn: rolesApi.list,
    staleTime: 10 * 60 * 1000, // 10 minutes — roles are near-static reference data
  });
}

/** Convenience: role_id -> role name, for table cells. Returns the raw
 * id as a fallback while roles are still loading/unavailable, so the
 * table never shows a blank cell. */
export function useRoleNameLookup(): (roleId: string) => string {
  const { data: roles } = useRoles();
  return (roleId: string) => roles?.find((r) => r.id === roleId)?.name ?? roleId;
}
