/**
 * Shared Create/Edit form — mode determined by the presence of
 * :schoolId in the route (matches /admin/schools/new vs.
 * /admin/schools/:schoolId exactly). One form component, not two
 * near-duplicate ones, since the fields are identical between create
 * and edit (only `status` is edit-only, since a school is always
 * created as "active" — matches SchoolCreateRequest not having a
 * status field, verified against the backend schema).
 */
import { useState, useEffect, type FormEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useSchool, useCreateSchool, useUpdateSchool, useDeleteSchool } from "@/hooks/useSchools";
import { useAuthStore } from "@/store/authStore";

export function SchoolFormPage() {
  const { schoolId } = useParams<{ schoolId: string }>();
  const isEditMode = !!schoolId;
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const canWrite = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const { data: school, isLoading, isError } = useSchool(schoolId);
  const createSchool = useCreateSchool();
  const updateSchool = useUpdateSchool(schoolId ?? "");
  const deleteSchool = useDeleteSchool();

  const [name, setName] = useState("");
  const [region, setRegion] = useState("");
  const [district, setDistrict] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [status, setStatus] = useState("active");
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  useEffect(() => {
    if (school) {
      setName(school.name);
      setRegion(school.region ?? "");
      setDistrict(school.district ?? "");
      setAddress(school.address ?? "");
      setPhone(school.phone ?? "");
      setStatus(school.status);
    }
  }, [school]);

  useEffect(() => {
    // Only the CREATE form is fully off-limits for a non-writer
    // (there is nothing to "view" at /admin/schools/new). Viewing an
    // EXISTING school (edit route, read-only rendering below) remains
    // available — the backend's GET /schools/{id} is public, so a
    // Moderator reading school details is a permitted action; only the
    // write controls are hidden (approved decision), not the read view.
    if (currentUser && !canWrite && !isEditMode) {
      navigate("/admin/schools", { replace: true });
    }
  }, [currentUser, canWrite, isEditMode, navigate]);

  if (!canWrite && !isEditMode) return null;
  if (isEditMode && isError) return <ErrorState title="Maktab" />;
  if (isEditMode && (isLoading || !school)) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const payload = {
      name,
      region: region || undefined,
      district: district || undefined,
      address: address || undefined,
      phone: phone || undefined,
    };
    if (isEditMode) {
      updateSchool.mutate({ ...payload, status }, { onSuccess: () => navigate(`/admin/schools/${schoolId}`) });
    } else {
      createSchool.mutate(payload, { onSuccess: () => navigate("/admin/schools") });
    }
  }

  function handleConfirmDelete() {
    if (!schoolId) return;
    deleteSchool.mutate(schoolId, { onSuccess: () => navigate("/admin/schools") });
  }

  const isSubmitting = createSchool.isPending || updateSchool.isPending;

  return (
    <div className="max-w-2xl">
      <button type="button" onClick={() => navigate("/admin/schools")} className="mb-4 text-sm text-primary hover:underline">
        ← Ro'yxatga qaytish
      </button>

      <Card>
        <CardHeader>
          <CardTitle>{!canWrite ? "Maktab ma'lumotlari" : isEditMode ? "Maktabni tahrirlash" : "Yangi maktab"}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* Non-writers (Moderator) see this same layout in read-only
              form — every input `disabled`, no Save/Delete buttons at
              all. This is a genuine read view, not a "visible but
              broken" action control (the thing the approved decision
              disallowed was disabled Create/Edit/Delete BUTTONS, not
              read-only display of data a Moderator is permitted to see). */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="name" className="mb-1 block text-sm font-medium text-foreground">Nomi</label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} disabled={!canWrite} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="region" className="mb-1 block text-sm font-medium text-foreground">Region</label>
                <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} disabled={!canWrite} />
              </div>
              <div>
                <label htmlFor="district" className="mb-1 block text-sm font-medium text-foreground">Tuman</label>
                <Input id="district" value={district} onChange={(e) => setDistrict(e.target.value)} disabled={!canWrite} />
              </div>
            </div>
            <div>
              <label htmlFor="address" className="mb-1 block text-sm font-medium text-foreground">Manzil</label>
              <Input id="address" value={address} onChange={(e) => setAddress(e.target.value)} disabled={!canWrite} />
            </div>
            <div>
              <label htmlFor="phone" className="mb-1 block text-sm font-medium text-foreground">Telefon</label>
              <Input id="phone" placeholder="+998712345678" value={phone} onChange={(e) => setPhone(e.target.value)} disabled={!canWrite} />
            </div>
            {isEditMode ? (
              <div>
                <label htmlFor="status" className="mb-1 block text-sm font-medium text-foreground">Holat</label>
                <select
                  id="status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  disabled={!canWrite}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm disabled:opacity-60"
                >
                  <option value="active">active</option>
                  <option value="inactive">inactive</option>
                  <option value="archived">archived</option>
                </select>
              </div>
            ) : null}

            {canWrite ? (
              <div className="flex items-center justify-between pt-2">
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Saqlanmoqda..." : "Saqlash"}
                </Button>
                {isEditMode ? (
                  <Button type="button" variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
                    O'chirish
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmDeleteOpen}
        title="Maktabni o'chirish"
        description={`"${name}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi.`}
        confirmLabel="O'chirish"
        isConfirming={deleteSchool.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setConfirmDeleteOpen(false)}
      />
    </div>
  );
}
