/**
 * Sprint 74 — Admin Exam Configuration UI. Nested under a Test
 * (/admin/tests/:testId/exam-config), same "has no meaning outside its
 * parent Test" rule TestQuestionsListPage.tsx already established for
 * Questions — no standalone top-level sidebar entry.
 *
 * RBAC: ExamSection/ExamModule/QuestionGroup endpoints require Admin or
 * Super Admin ONLY (verified in tests/router.py's require_roles calls —
 * stricter than Test/Question, which also allow Teacher). Unlike
 * TestsListPage/QuestionFormPage's canWrite pattern (which only hides
 * write actions), a non-Admin/Super-Admin here would get a 403 on
 * every GET too, so the whole page redirects away for anyone else —
 * hiding the entry point (done in TestsListPage.tsx) is a UX nicety,
 * this redirect is the real guard, and the backend's own require_roles
 * remains the actual enforcement either way.
 *
 * Data shape: Test -> ExamSection -> ExamModule -> QuestionGroup
 * (QuestionGroup is test-scoped, optionally also tied to one module).
 * Modules for the WHOLE test are fetched once (Sprint 74 backend
 * addition, GET /tests/exam-modules?test_id=) and grouped client-side
 * by section_id — avoids one HTTP request per section.
 *
 * Routing configuration (Section G of the Sprint 74 brief): only
 * routing_group/routing_variant are shown/editable here — these are
 * the ONLY routing-related fields that genuinely exist and are
 * readable/writable through a verified endpoint (ExamModule's own
 * Create/Update schema, Sprint 48). PerformanceThresholdRoutingStrategy
 * is not wired into live attempt execution and there is no persistent
 * threshold-rule storage/endpoint — this sprint does not invent one or
 * claim adaptive routing is operational.
 *
 * Question assignment (section F) is NOT duplicated here — it is done
 * on each question's own edit page (QuestionFormPage.tsx), which this
 * page links to, reusing the existing Questions list/form rather than
 * building a second question-editing surface.
 */
import { useEffect, useId, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/layout/ErrorState";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { useTest } from "@/hooks/useTests";
import {
  useCreateExamModule,
  useCreateExamSection,
  useCreateQuestionGroup,
  useCreateRoutingThresholdRule,
  useDeleteQuestionGroup,
  useDeleteRoutingThresholdRule,
  useExamModulesForTest,
  useExamSectionsList,
  useQuestionGroupsList,
  useRoutingThresholdRulesList,
  useUpdateExamModule,
  useUpdateExamSection,
  useUpdateQuestionGroup,
  useUpdateRoutingThresholdRule,
} from "@/hooks/useExamConfig";
import { useAuthStore } from "@/store/authStore";
import type { ExamModuleOut, ExamSectionOut, QuestionGroupOut, RoutingThresholdRuleOut } from "@/api/examConfig";

function emptyToUndefined(v: string): string | undefined {
  return v.trim() === "" ? undefined : v;
}

// --- Section form (shared by "add" and inline "edit") ---

interface SectionFormValues {
  name: string;
  order_number: number;
  duration: string;
}

function SectionForm({
  initial,
  isSaving,
  onSubmit,
  onCancel,
}: {
  initial: SectionFormValues;
  isSaving: boolean;
  onSubmit: (values: SectionFormValues) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState(initial);
  const id = useId();

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        onSubmit(values);
      }}
      className="grid grid-cols-1 gap-2 sm:grid-cols-[2fr_1fr_1fr_auto] sm:items-end"
    >
      <div>
        <label htmlFor={`${id}-name`} className="mb-1 block text-xs font-medium text-foreground/70">Nomi</label>
        <Input
          id={`${id}-name`}
          value={values.name}
          onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))}
          required
          minLength={1}
        />
      </div>
      <div>
        <label htmlFor={`${id}-order`} className="mb-1 block text-xs font-medium text-foreground/70">Tartib raqami</label>
        <Input
          id={`${id}-order`}
          type="number"
          min={0}
          value={values.order_number}
          onChange={(e) => setValues((v) => ({ ...v, order_number: Number(e.target.value) }))}
        />
      </div>
      <div>
        <label htmlFor={`${id}-duration`} className="mb-1 block text-xs font-medium text-foreground/70">Davomiyligi (daq, ixtiyoriy)</label>
        <Input
          id={`${id}-duration`}
          type="number"
          min={1}
          value={values.duration}
          onChange={(e) => setValues((v) => ({ ...v, duration: e.target.value }))}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={isSaving}>{isSaving ? "..." : "Saqlash"}</Button>
        {onCancel ? <Button type="button" variant="outline" onClick={onCancel}>Bekor qilish</Button> : null}
      </div>
    </form>
  );
}

// --- Module form (shared by "add" and inline "edit") ---

interface ModuleFormValues {
  name: string;
  order_number: number;
  duration: string;
  difficulty_tier: string;
  routing_group: string;
  routing_variant: string;
}

function ModuleForm({
  initial,
  isSaving,
  onSubmit,
  onCancel,
}: {
  initial: ModuleFormValues;
  isSaving: boolean;
  onSubmit: (values: ModuleFormValues) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState(initial);
  const id = useId();

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        onSubmit(values);
      }}
      className="space-y-2 rounded-md border border-border bg-primary/5 p-3"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div>
          <label htmlFor={`${id}-name`} className="mb-1 block text-xs font-medium text-foreground/70">Nomi</label>
          <Input id={`${id}-name`} value={values.name} onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))} required minLength={1} />
        </div>
        <div>
          <label htmlFor={`${id}-order`} className="mb-1 block text-xs font-medium text-foreground/70">Tartib raqami</label>
          <Input
            id={`${id}-order`}
            type="number"
            min={0}
            value={values.order_number}
            onChange={(e) => setValues((v) => ({ ...v, order_number: Number(e.target.value) }))}
          />
        </div>
        <div>
          <label htmlFor={`${id}-duration`} className="mb-1 block text-xs font-medium text-foreground/70">Davomiyligi (daq, ixtiyoriy)</label>
          <Input id={`${id}-duration`} type="number" min={1} value={values.duration} onChange={(e) => setValues((v) => ({ ...v, duration: e.target.value }))} />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div>
          <label htmlFor={`${id}-tier`} className="mb-1 block text-xs font-medium text-foreground/70">Qiyinlik darajasi (ixtiyoriy)</label>
          <Input id={`${id}-tier`} value={values.difficulty_tier} onChange={(e) => setValues((v) => ({ ...v, difficulty_tier: e.target.value }))} />
        </div>
        <div>
          <label htmlFor={`${id}-rgroup`} className="mb-1 block text-xs font-medium text-foreground/70">routing_group (ixtiyoriy)</label>
          <Input id={`${id}-rgroup`} value={values.routing_group} onChange={(e) => setValues((v) => ({ ...v, routing_group: e.target.value }))} />
        </div>
        <div>
          <label htmlFor={`${id}-rvariant`} className="mb-1 block text-xs font-medium text-foreground/70">routing_variant (ixtiyoriy)</label>
          <Input id={`${id}-rvariant`} value={values.routing_variant} onChange={(e) => setValues((v) => ({ ...v, routing_variant: e.target.value }))} />
        </div>
      </div>
      <p className="text-xs text-foreground/50">
        routing_group/routing_variant — kelajakdagi adaptiv yo'naltirish uchun metama'lumot. Bu maydonlar hozircha
        hech qanday avtomatik yo'naltirish qarorida ishlatilmaydi (adaptiv yo'naltirish hali haqiqiy ijroga ulanmagan).
      </p>
      <div className="flex gap-2">
        <Button type="submit" disabled={isSaving}>{isSaving ? "..." : "Saqlash"}</Button>
        {onCancel ? <Button type="button" variant="outline" onClick={onCancel}>Bekor qilish</Button> : null}
      </div>
    </form>
  );
}

// --- Group form (shared by "add" and inline "edit") ---

interface GroupFormValues {
  title: string;
  order_number: number;
  stimulus_text: string;
  module_id: string;
}

function GroupForm({
  initial,
  modules,
  isSaving,
  onSubmit,
  onCancel,
}: {
  initial: GroupFormValues;
  modules: ExamModuleOut[];
  isSaving: boolean;
  onSubmit: (values: GroupFormValues) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState(initial);
  const id = useId();

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        onSubmit(values);
      }}
      className="space-y-2 rounded-md border border-border p-3"
    >
      <div>
        <label htmlFor={`${id}-title`} className="mb-1 block text-xs font-medium text-foreground/70">Sarlavha</label>
        <Input id={`${id}-title`} value={values.title} onChange={(e) => setValues((v) => ({ ...v, title: e.target.value }))} required minLength={1} />
      </div>
      <div>
        <label htmlFor={`${id}-stimulus`} className="mb-1 block text-xs font-medium text-foreground/70">Stimul matni (ixtiyoriy)</label>
        <textarea
          id={`${id}-stimulus`}
          value={values.stimulus_text}
          onChange={(e) => setValues((v) => ({ ...v, stimulus_text: e.target.value }))}
          rows={3}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        />
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <label htmlFor={`${id}-order`} className="mb-1 block text-xs font-medium text-foreground/70">Tartib raqami</label>
          <Input
            id={`${id}-order`}
            type="number"
            min={0}
            value={values.order_number}
            onChange={(e) => setValues((v) => ({ ...v, order_number: Number(e.target.value) }))}
          />
        </div>
        <div>
          <label htmlFor={`${id}-module`} className="mb-1 block text-xs font-medium text-foreground/70">Modul (ixtiyoriy)</label>
          <select
            id={`${id}-module`}
            value={values.module_id}
            onChange={(e) => setValues((v) => ({ ...v, module_id: e.target.value }))}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">— testga bog'langan (modulsiz) —</option>
            {modules.map((m) => (
              <option key={m.id} value={m.id}>{m.name}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={isSaving}>{isSaving ? "..." : "Saqlash"}</Button>
        {onCancel ? <Button type="button" variant="outline" onClick={onCancel}>Bekor qilish</Button> : null}
      </div>
    </form>
  );
}

// --- Adaptive Routing Rule form (Sprint 75 completion) ---

interface RuleFormValues {
  routing_group: string;
  min_ratio: string;
  variant: string;
}

/** Phase 4 — frontend validation mirroring the backend's own rules
 * exactly (routing_group/variant required, 0 <= min_ratio <= 1). The
 * backend remains authoritative — this only avoids an obviously-invalid
 * round trip; a value that somehow slips past this still gets a clean
 * 422 from RoutingThresholdRuleCreateRequest/UpdateRequest. */
function validateRuleForm(values: RuleFormValues): string | null {
  if (values.routing_group.trim() === "") return "routing_group talab qilinadi";
  if (values.variant.trim() === "") return "Maqsadli variant (routing_variant) talab qilinadi";
  if (values.min_ratio.trim() === "") return "Minimal nisbat (min_ratio) talab qilinadi";
  const ratio = Number(values.min_ratio);
  if (Number.isNaN(ratio)) return "Minimal nisbat (min_ratio) raqam bo'lishi kerak";
  if (ratio < 0 || ratio > 1) return "Minimal nisbat (min_ratio) 0 va 1 orasida bo'lishi kerak";
  return null;
}

function RuleForm({
  initial,
  isSaving,
  onSubmit,
  onCancel,
}: {
  initial: RuleFormValues;
  isSaving: boolean;
  onSubmit: (values: RuleFormValues) => void;
  onCancel?: () => void;
}) {
  const [values, setValues] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  return (
    <form
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        const validationError = validateRuleForm(values);
        if (validationError) {
          setError(validationError);
          return;
        }
        setError(null);
        onSubmit(values);
      }}
      noValidate
      className="space-y-2 rounded-md border border-border bg-primary/5 p-3"
    >
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div>
          <label htmlFor={`${id}-group`} className="mb-1 block text-xs font-medium text-foreground/70">routing_group</label>
          <Input
            id={`${id}-group`}
            value={values.routing_group}
            onChange={(e) => setValues((v) => ({ ...v, routing_group: e.target.value }))}
            required
            minLength={1}
          />
        </div>
        <div>
          <label htmlFor={`${id}-ratio`} className="mb-1 block text-xs font-medium text-foreground/70">Minimal nisbat (0.00 – 1.00)</label>
          <Input
            id={`${id}-ratio`}
            type="number"
            min={0}
            max={1}
            step={0.01}
            value={values.min_ratio}
            onChange={(e) => setValues((v) => ({ ...v, min_ratio: e.target.value }))}
            required
          />
        </div>
        <div>
          <label htmlFor={`${id}-variant`} className="mb-1 block text-xs font-medium text-foreground/70">Maqsadli variant (routing_variant)</label>
          <Input
            id={`${id}-variant`}
            value={values.variant}
            onChange={(e) => setValues((v) => ({ ...v, variant: e.target.value }))}
            required
            minLength={1}
          />
        </div>
      </div>
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
      <div className="flex gap-2">
        <Button type="submit" disabled={isSaving}>{isSaving ? "..." : "Saqlash"}</Button>
        {onCancel ? <Button type="button" variant="outline" onClick={onCancel}>Bekor qilish</Button> : null}
      </div>
    </form>
  );
}

export function ExamConfigPage({ basePath = "/admin" }: { basePath?: string }) {
  const { testId } = useParams<{ testId: string }>();
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  // Stricter than Tests/Questions' own canWrite — ExamSection/ExamModule/
  // QuestionGroup require Admin/Super Admin for EVERY operation,
  // including reads (verified in the backend router).
  const canConfigureExam = currentUser?.role === "Admin" || currentUser?.role === "Super Admin";

  const { data: test, isLoading: testLoading, isError: testIsError } = useTest(testId);
  const { data: sections, isLoading: sectionsLoading, isError: sectionsIsError } = useExamSectionsList(canConfigureExam ? testId : undefined);
  const { data: modules, isError: modulesIsError } = useExamModulesForTest(canConfigureExam ? testId : undefined);
  const { data: groups, isError: groupsIsError } = useQuestionGroupsList(canConfigureExam ? testId : undefined);
  const { data: rules, isError: rulesIsError } = useRoutingThresholdRulesList(canConfigureExam ? testId : undefined);

  const createSection = useCreateExamSection();
  const updateSection = useUpdateExamSection(testId ?? "");
  const createModule = useCreateExamModule(testId ?? "");
  const updateModule = useUpdateExamModule(testId ?? "");
  const createGroup = useCreateQuestionGroup(testId ?? "");
  const updateGroup = useUpdateQuestionGroup(testId ?? "");
  const deleteGroup = useDeleteQuestionGroup(testId ?? "");
  const createRule = useCreateRoutingThresholdRule(testId ?? "");
  const updateRule = useUpdateRoutingThresholdRule(testId ?? "");
  const deleteRule = useDeleteRoutingThresholdRule(testId ?? "");

  const [addingSection, setAddingSection] = useState(false);
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null);
  const [expandedSectionId, setExpandedSectionId] = useState<string | null>(null);
  const [addingModuleForSection, setAddingModuleForSection] = useState<string | null>(null);
  const [editingModuleId, setEditingModuleId] = useState<string | null>(null);
  const [addingGroup, setAddingGroup] = useState(false);
  const [editingGroupId, setEditingGroupId] = useState<string | null>(null);
  const [pendingDeleteGroup, setPendingDeleteGroup] = useState<QuestionGroupOut | null>(null);
  const [addingRule, setAddingRule] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
  const [pendingDeleteRule, setPendingDeleteRule] = useState<RoutingThresholdRuleOut | null>(null);

  useEffect(() => {
    if (currentUser && !canConfigureExam) {
      navigate(`${basePath}/tests`, { replace: true });
    }
  }, [currentUser, canConfigureExam, navigate, basePath]);

  if (!testId) return null;
  if (!canConfigureExam) return null;
  if (testIsError || sectionsIsError || modulesIsError || groupsIsError || rulesIsError) return <ErrorState title="Imtihon tuzilmasi" />;
  if (testLoading || !test) return <p className="text-sm text-foreground/50">Yuklanmoqda...</p>;

  const sortedSections = [...(sections ?? [])].sort((a, b) => a.order_number - b.order_number);
  const allModules = modules ?? [];
  const sortedGroups = [...(groups ?? [])].sort((a, b) => a.order_number - b.order_number);
  const sortedRules = [...(rules ?? [])].sort((a, b) => a.routing_group.localeCompare(b.routing_group) || a.min_ratio - b.min_ratio);
  const moduleName = (moduleId: string | null) => (moduleId ? allModules.find((m) => m.id === moduleId)?.name ?? moduleId : "—");

  function modulesForSection(sectionId: string): ExamModuleOut[] {
    return allModules.filter((m) => m.section_id === sectionId).sort((a, b) => a.order_number - b.order_number);
  }

  function handleCreateSection(values: SectionFormValues) {
    if (!testId) return;
    createSection.mutate(
      { test_id: testId, name: values.name, order_number: values.order_number, duration: values.duration ? Number(values.duration) : undefined },
      { onSuccess: () => setAddingSection(false) },
    );
  }

  function handleUpdateSection(section: ExamSectionOut, values: SectionFormValues) {
    updateSection.mutate(
      {
        sectionId: section.id,
        data: { name: values.name, order_number: values.order_number, duration: values.duration ? Number(values.duration) : null },
      },
      { onSuccess: () => setEditingSectionId(null) },
    );
  }

  function handleCreateModule(sectionId: string, values: ModuleFormValues) {
    createModule.mutate(
      {
        section_id: sectionId,
        name: values.name,
        order_number: values.order_number,
        duration: values.duration ? Number(values.duration) : undefined,
        difficulty_tier: emptyToUndefined(values.difficulty_tier),
        routing_group: emptyToUndefined(values.routing_group),
        routing_variant: emptyToUndefined(values.routing_variant),
      },
      { onSuccess: () => setAddingModuleForSection(null) },
    );
  }

  function handleUpdateModule(moduleId: string, values: ModuleFormValues) {
    updateModule.mutate(
      {
        moduleId,
        data: {
          name: values.name,
          order_number: values.order_number,
          duration: values.duration ? Number(values.duration) : null,
          difficulty_tier: values.difficulty_tier.trim() === "" ? null : values.difficulty_tier,
          routing_group: values.routing_group.trim() === "" ? null : values.routing_group,
          routing_variant: values.routing_variant.trim() === "" ? null : values.routing_variant,
        },
      },
      { onSuccess: () => setEditingModuleId(null) },
    );
  }

  function handleCreateGroup(values: GroupFormValues) {
    if (!testId) return;
    createGroup.mutate(
      {
        test_id: testId,
        title: values.title,
        order_number: values.order_number,
        stimulus_text: emptyToUndefined(values.stimulus_text),
        module_id: emptyToUndefined(values.module_id),
      },
      { onSuccess: () => setAddingGroup(false) },
    );
  }

  function handleUpdateGroup(group: QuestionGroupOut, values: GroupFormValues) {
    updateGroup.mutate(
      {
        groupId: group.id,
        data: {
          title: values.title,
          order_number: values.order_number,
          stimulus_text: values.stimulus_text.trim() === "" ? null : values.stimulus_text,
          module_id: values.module_id === "" ? null : values.module_id,
        },
      },
      { onSuccess: () => setEditingGroupId(null) },
    );
  }

  function handleConfirmDeleteGroup() {
    if (!pendingDeleteGroup) return;
    deleteGroup.mutate(pendingDeleteGroup.id, { onSuccess: () => setPendingDeleteGroup(null) });
  }

  function handleCreateRule(values: RuleFormValues) {
    if (!testId) return;
    createRule.mutate(
      { test_id: testId, routing_group: values.routing_group, min_ratio: Number(values.min_ratio), variant: values.variant },
      { onSuccess: () => setAddingRule(false) },
    );
  }

  function handleUpdateRule(rule: RoutingThresholdRuleOut, values: RuleFormValues) {
    updateRule.mutate(
      { ruleId: rule.id, data: { routing_group: values.routing_group, min_ratio: Number(values.min_ratio), variant: values.variant } },
      { onSuccess: () => setEditingRuleId(null) },
    );
  }

  function handleConfirmDeleteRule() {
    if (!pendingDeleteRule) return;
    deleteRule.mutate(pendingDeleteRule.id, { onSuccess: () => setPendingDeleteRule(null) });
  }

  return (
    <div className="max-w-4xl space-y-6">
      <button type="button" onClick={() => navigate(`${basePath}/tests`)} className="text-sm text-primary hover:underline">
        ← Testlarga qaytish
      </button>

      <div>
        <h1 className="text-xl font-semibold text-foreground">Imtihon tuzilmasi</h1>
        <p className="text-sm text-foreground/60">{test.title}</p>
      </div>

      {/* --- Sections --- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Bo'limlar (Sections)</CardTitle>
          {!addingSection ? (
            <Button type="button" variant="outline" onClick={() => setAddingSection(true)}>+ Bo'lim qo'shish</Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-4">
          {addingSection ? (
            <SectionForm
              initial={{ name: "", order_number: sortedSections.length, duration: "" }}
              isSaving={createSection.isPending}
              onSubmit={handleCreateSection}
              onCancel={() => setAddingSection(false)}
            />
          ) : null}

          {sectionsLoading ? (
            <p className="text-sm text-foreground/50">Yuklanmoqda...</p>
          ) : sortedSections.length === 0 ? (
            <p className="text-sm text-foreground/50">
              Bu test uchun hali bo'lim yo'q. Bo'limsiz test to'liq ishlayveradi — bo'lim/modul faqat SAT/IELTS kabi
              ko'p bosqichli imtihonlar uchun kerak bo'ladi.
            </p>
          ) : (
            <div className="space-y-3">
              {sortedSections.map((section) => (
                <div key={section.id} className="rounded-md border border-border p-3">
                  {editingSectionId === section.id ? (
                    <SectionForm
                      initial={{ name: section.name, order_number: section.order_number, duration: section.duration ? String(section.duration) : "" }}
                      isSaving={updateSection.isPending}
                      onSubmit={(values) => handleUpdateSection(section, values)}
                      onCancel={() => setEditingSectionId(null)}
                    />
                  ) : (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-foreground">{section.name}</p>
                        <p className="text-xs text-foreground/50">
                          Tartib: {section.order_number}{section.duration ? ` · ${section.duration} daq` : ""}
                        </p>
                      </div>
                      <div className="flex gap-3">
                        <button
                          type="button"
                          onClick={() => setExpandedSectionId((id) => (id === section.id ? null : section.id))}
                          className="text-sm text-primary hover:underline"
                        >
                          {expandedSectionId === section.id ? "Modullarni yashirish" : `Modullar (${modulesForSection(section.id).length})`}
                        </button>
                        <button type="button" onClick={() => setEditingSectionId(section.id)} className="text-sm text-primary hover:underline">
                          Tahrirlash
                        </button>
                      </div>
                    </div>
                  )}

                  {expandedSectionId === section.id ? (
                    <div className="mt-3 space-y-2 border-t border-border pt-3 pl-3">
                      {modulesForSection(section.id).length === 0 ? (
                        <p className="text-sm text-foreground/50">Bu bo'limda hali modul yo'q.</p>
                      ) : (
                        modulesForSection(section.id).map((module) =>
                          editingModuleId === module.id ? (
                            <ModuleForm
                              key={module.id}
                              initial={{
                                name: module.name,
                                order_number: module.order_number,
                                duration: module.duration ? String(module.duration) : "",
                                difficulty_tier: module.difficulty_tier ?? "",
                                routing_group: module.routing_group ?? "",
                                routing_variant: module.routing_variant ?? "",
                              }}
                              isSaving={updateModule.isPending}
                              onSubmit={(values) => handleUpdateModule(module.id, values)}
                              onCancel={() => setEditingModuleId(null)}
                            />
                          ) : (
                            <div key={module.id} className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2">
                              <div>
                                <p className="text-sm font-medium text-foreground">{module.name}</p>
                                <p className="text-xs text-foreground/50">
                                  Tartib: {module.order_number}
                                  {module.duration ? ` · ${module.duration} daq` : ""}
                                  {module.routing_group ? ` · routing_group: ${module.routing_group}` : ""}
                                  {module.routing_variant ? ` · routing_variant: ${module.routing_variant}` : ""}
                                </p>
                              </div>
                              <button type="button" onClick={() => setEditingModuleId(module.id)} className="text-sm text-primary hover:underline">
                                Tahrirlash
                              </button>
                            </div>
                          ),
                        )
                      )}

                      {addingModuleForSection === section.id ? (
                        <ModuleForm
                          initial={{ name: "", order_number: modulesForSection(section.id).length, duration: "", difficulty_tier: "", routing_group: "", routing_variant: "" }}
                          isSaving={createModule.isPending}
                          onSubmit={(values) => handleCreateModule(section.id, values)}
                          onCancel={() => setAddingModuleForSection(null)}
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => setAddingModuleForSection(section.id)}
                          className="text-sm text-primary hover:underline"
                        >
                          + Modul qo'shish
                        </button>
                      )}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* --- Question Groups --- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Guruhlar (umumiy stimul)</CardTitle>
          {!addingGroup ? (
            <Button type="button" variant="outline" onClick={() => setAddingGroup(true)}>+ Guruh qo'shish</Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3">
          {addingGroup ? (
            <GroupForm
              initial={{ title: "", order_number: sortedGroups.length, stimulus_text: "", module_id: "" }}
              modules={allModules}
              isSaving={createGroup.isPending}
              onSubmit={handleCreateGroup}
              onCancel={() => setAddingGroup(false)}
            />
          ) : null}

          {sortedGroups.length === 0 ? (
            <p className="text-sm text-foreground/50">
              Bu test uchun hali guruh yo'q. Guruh — bir nechta savol bog'langan umumiy matn/audio (masalan, IELTS
              Reading passage).
            </p>
          ) : (
            sortedGroups.map((group) =>
              editingGroupId === group.id ? (
                <GroupForm
                  key={group.id}
                  initial={{
                    title: group.title,
                    order_number: group.order_number,
                    stimulus_text: group.stimulus_text ?? "",
                    module_id: group.module_id ?? "",
                  }}
                  modules={allModules}
                  isSaving={updateGroup.isPending}
                  onSubmit={(values) => handleUpdateGroup(group, values)}
                  onCancel={() => setEditingGroupId(null)}
                />
              ) : (
                <div key={group.id} className="flex items-center justify-between rounded-md border border-border p-3">
                  <div>
                    <p className="font-medium text-foreground">{group.title}</p>
                    <p className="text-xs text-foreground/50">
                      Tartib: {group.order_number} · Modul: {moduleName(group.module_id)}
                    </p>
                    {group.stimulus_text ? <p className="mt-1 max-w-md truncate text-xs text-foreground/50">{group.stimulus_text}</p> : null}
                  </div>
                  <div className="flex gap-3">
                    <button type="button" onClick={() => setEditingGroupId(group.id)} className="text-sm text-primary hover:underline">
                      Tahrirlash
                    </button>
                    <button type="button" onClick={() => setPendingDeleteGroup(group)} className="text-sm text-destructive hover:underline">
                      O'chirish
                    </button>
                  </div>
                </div>
              ),
            )
          )}
        </CardContent>
      </Card>

      {/* --- Adaptive Routing Rules (Sprint 75 completion) --- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Adaptiv yo'naltirish qoidalari</CardTitle>
          {!addingRule ? (
            <Button type="button" variant="outline" onClick={() => setAddingRule(true)}>+ Qoida qo'shish</Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-xs text-foreground/50">
            Bir modul yakunlangach, agar ushbu modulning routing_group qiymati uchun qoida mavjud bo'lsa, talabgor
            ushbu modulda to'g'ri javoblar nisbati (natija) qoidadagi minimal nisbatdan katta yoki teng bo'lgan eng
            yuqori qoidaga mos keluvchi variantga yo'naltiriladi. Hech qanday qoida mos kelmasa, odatiy ketma-ket
            tartib ishlatiladi — mavjud testlarning hech biri bu bilan o'zgarmaydi, chunki ularda hali qoida yo'q.
          </p>

          {addingRule ? (
            <RuleForm
              initial={{ routing_group: "", min_ratio: "", variant: "" }}
              isSaving={createRule.isPending}
              onSubmit={handleCreateRule}
              onCancel={() => setAddingRule(false)}
            />
          ) : null}

          {sortedRules.length === 0 ? (
            <p className="text-sm text-foreground/50">
              Bu test uchun hali adaptiv yo'naltirish qoidasi yo'q. Qoida qo'shilmaguncha bu test odatiy ketma-ket
              tartibda ishlayveradi.
            </p>
          ) : (
            sortedRules.map((rule) =>
              editingRuleId === rule.id ? (
                <RuleForm
                  key={rule.id}
                  initial={{ routing_group: rule.routing_group, min_ratio: String(rule.min_ratio), variant: rule.variant }}
                  isSaving={updateRule.isPending}
                  onSubmit={(values) => handleUpdateRule(rule, values)}
                  onCancel={() => setEditingRuleId(null)}
                />
              ) : (
                <div key={rule.id} className="flex items-center justify-between rounded-md border border-border p-3">
                  <div>
                    <p className="text-sm text-foreground/50">Routing group: <span className="font-medium text-foreground">{rule.routing_group}</span></p>
                    <p className="text-sm text-foreground/50">Minimal nisbat: <span className="font-medium text-foreground">{rule.min_ratio.toFixed(2)}</span></p>
                    <p className="text-sm text-foreground/50">Maqsadli variant: <span className="font-medium text-foreground">{rule.variant}</span></p>
                  </div>
                  <div className="flex gap-3">
                    <button type="button" onClick={() => setEditingRuleId(rule.id)} className="text-sm text-primary hover:underline">
                      Tahrirlash
                    </button>
                    <button type="button" onClick={() => setPendingDeleteRule(rule)} className="text-sm text-destructive hover:underline">
                      O'chirish
                    </button>
                  </div>
                </div>
              ),
            )
          )}
        </CardContent>
      </Card>

      {/* --- Questions (assignment happens on each question's own edit page) --- */}
      <Card>
        <CardHeader>
          <CardTitle>Savollarni biriktirish</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-foreground/60">
            Har bir savolni bo'lim/modul/guruhga biriktirish uchun savolni tahrirlash sahifasini oching.
          </p>
          <Button type="button" variant="outline" onClick={() => navigate(`${basePath}/tests/${testId}/questions`)}>
            Savollar ro'yxatini ochish
          </Button>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={pendingDeleteGroup !== null}
        title="Guruhni o'chirish"
        description={
          pendingDeleteGroup
            ? `"${pendingDeleteGroup.title}" o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi. Bu guruhga biriktirilgan savollar o'chirilmaydi — ularning group_id maydoni bo'sh qoladi.`
            : ""
        }
        confirmLabel="O'chirish"
        isConfirming={deleteGroup.isPending}
        onConfirm={handleConfirmDeleteGroup}
        onCancel={() => setPendingDeleteGroup(null)}
      />

      <ConfirmDialog
        open={pendingDeleteRule !== null}
        title="Yo'naltirish qoidasini o'chirish"
        description={
          pendingDeleteRule
            ? `Routing group "${pendingDeleteRule.routing_group}" (minimal nisbat ${pendingDeleteRule.min_ratio.toFixed(2)}) qoidasi o'chirilsinmi? Bu amalni orqaga qaytarib bo'lmaydi. O'chirilgandan so'ng ushbu qoida hech qanday faol/yangi urinishda ishlatilmaydi.`
            : ""
        }
        confirmLabel="O'chirish"
        isConfirming={deleteRule.isPending}
        onConfirm={handleConfirmDeleteRule}
        onCancel={() => setPendingDeleteRule(null)}
      />
    </div>
  );
}
