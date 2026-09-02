# Sprint 19 — Tests & Questions UI: Architecture Impact Analysis

**Status: Approved and implemented.**

## Key findings, established before any design choice below

**1. "Test ↔ Lesson relationship" (originally requested) does not exist on the backend — corrected, not assumed.** Verified exhaustively against `TestCreateRequest`/`TestUpdateRequest`/`TestOut`/`TestListParams`: Tests relate to `subject_id`, `grade_id`, `topic_id` (all optional, independently nullable) — there is no `lesson_id` field anywhere in the Tests module. A Test and a Lesson are siblings under Topic, not parent/child.

**2. Tests have a documented state machine with an unreachable transition.** `ALLOWED_STATUS_TRANSITIONS` (`draft → published/archived`, `published → archived`) exists in `constants.py`, but only `POST /{id}/publish` exists as an endpoint — verified exhaustively against the router (5 endpoints: list, get, create, update, publish, delete). No `archive_test` method exists in the service, no endpoint reaches the `archived` state.

**3. Question Media is a plain URL field, not a file-upload flow.** `MediaCreateRequest.file_url: str` (validated as a URL, same shape as Lessons' `video`/`pdf`) — does not reference the `uploads` module at all.

**4. Options are created NESTED and atomic with the Question, then managed via separate granular sub-resource endpoints afterward.** `QuestionCreateRequest.options: list[OptionCreateRequest]` — the initial option set is submitted as part of the single `POST /questions` call. After creation, `POST/PATCH/DELETE /questions/{id}/options/{option_id}` exist as their own endpoints.

**5. A real, non-trivial cross-field validation rule** (`validate_option_set`, service-layer): `essay`/`short_answer` need zero options; `single_choice`/`true_false` need ≥2 options with exactly 1 marked correct; `multiple_choice` needs ≥2 options with at least 1 correct.

**6. `api/tests.ts` already existed** (Sprint 14's `publishedCount()`) — extended, not replaced. `api/questions.ts` did not exist — new file.

**7. Media has no update endpoint** — `add_media`/`delete_media` only, no `PATCH .../media/{media_id}`.

**8. Tests' real status enum is `draft/published/archived`** (`TestStatus` in `models.py`), not the generic `active/inactive/archived` set every prior module shared.

---

## Approved Decisions (implemented)

1. **Test ↔ Lesson**: frontend strictly follows the real backend model — Test relates only to Subject/Grade/Topic, all optional, all remain editable post-creation. No Lesson relationship built.
2. **Archive**: not built. Only Publish (draft→published) and Delete, matching what the API actually supports.
3. **Question Media**: no `uploads` module integration — plain URL field only.
4. **Questions routing**: nested under a Test — `/admin/tests/:testId/questions` — not a standalone top-level module, no independent sidebar entry.
5. **Media badges**: `components/lessons/ContentBadges.tsx` (Sprint 18) left unmodified. A new, independent `components/questions/MediaTypeBadges.tsx` was built instead, covering Media's real 4-value type set (`image/audio/video/formula`).
6. **Options editor**: all edits (add/remove/edit-text/toggle-correct) accumulate in local component state only. Sent to the backend only on "Saqlash". New Questions use nested `options` in the single create call; existing Questions' option changes are diffed against the original snapshot and executed via the real granular endpoints.
7. **Validation**: `single_choice`/`true_false` require exactly 1 correct option; `multiple_choice` requires at least 1 — checked on submit, the Submit button is never disabled, and no malformed request reaches the backend when the check fails.
8. **React Query cache**: Question Option/Media mutations invalidate only Questions' own cache keys (`["questions", ...]`) — Test cache (`["tests", ...]`) is never touched by these mutations.

**Confirmed RBAC** (verified against real backend `require_roles(...)`): Tests and Questions (including Options/Media) — Create/Edit/Delete = Super Admin, Admin, Teacher. Everyone else (including Student) = read-only.

---

## Risks (as identified pre-implementation)

| Risk | Severity | Outcome |
|---|---|---|
| Conditional option-set validation built incompletely | High | Mitigated — mirrors backend's exact message text, tested explicitly per question_type |
| Dual-mode Options editor (new vs. existing rows) conflated | High | Mitigated — diff computed against an explicit original-snapshot, not in-place flags |
| Naive cache invalidation touching Test cache from Option/Media mutations | Medium | Mitigated — verified directly, no code reference to `["tests", ...]` in `useQuestions.ts` |
| No prior nested-route convention | Medium | Resolved — `/admin/tests/:testId/questions` established as the pattern |
| Archive action mistakenly built | Medium | Avoided — no Archive UI exists |
| `ContentBadges` reuse ambiguity | Low | Resolved — new `MediaTypeBadges` built instead |
