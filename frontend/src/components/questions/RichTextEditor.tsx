/**
 * Sprint 33 — a deliberately minimal, dependency-free rich text
 * editor. `document.execCommand` is deprecated but still broadly
 * supported for exactly this narrow use case (bold/italic/underline/
 * lists/links/undo-redo on a contentEditable div) — chosen over adding
 * a heavy new editor library (TipTap/Slate/Quill) given the "eng
 * yengil va ishonchli variantni tanla" instruction and this sprint's
 * real time budget. The HTML this produces is NEVER trusted as-is —
 * the backend's Sprint 32 `bleach` sanitizer is the actual security
 * boundary; this component only controls what a well-behaved user CAN
 * produce via its own toolbar, not what a malicious client could send
 * directly to the API.
 *
 * Formula insertion: a "Formula" button wraps the current selection
 * (or inserts a placeholder) in `$...$` delimiters — plain text, not
 * HTML — which QuestionPreview.tsx renders via KaTeX. This keeps
 * LaTeX authoring simple (type between $ signs) without building a
 * live math-input widget, matching the explicit permission to keep
 * formula support to "input/preview" rather than a full editor.
 */
import { useEffect, useRef } from "react";

interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  ariaLabel: string;
  minHeightClassName?: string;
  disabled?: boolean;
}

const TOOLBAR_BUTTONS: Array<{ label: string; command: string; title: string }> = [
  { label: "B", command: "bold", title: "Qalin" },
  { label: "I", command: "italic", title: "Qiya" },
  { label: "U", command: "underline", title: "Tagiga chizilgan" },
];

export function RichTextEditor({ value, onChange, placeholder, ariaLabel, minHeightClassName = "min-h-[120px]", disabled }: RichTextEditorProps) {
  const editorRef = useRef<HTMLDivElement>(null);
  const isInternalUpdate = useRef(false);

  // Keeps the contentEditable DOM in sync with external value changes
  // (e.g. loading an existing question) WITHOUT fighting the browser's
  // own cursor position on every keystroke — only syncs when the
  // change didn't originate from this editor's own onInput.
  useEffect(() => {
    if (editorRef.current && !isInternalUpdate.current && editorRef.current.innerHTML !== value) {
      editorRef.current.innerHTML = value;
    }
    isInternalUpdate.current = false;
  }, [value]);

  function exec(command: string, arg?: string) {
    editorRef.current?.focus();
    document.execCommand(command, false, arg);
    handleInput();
  }

  function handleInput() {
    if (!editorRef.current) return;
    isInternalUpdate.current = true;
    onChange(editorRef.current.innerHTML);
  }

  function insertHeading(level: "h2" | "h3") {
    exec("formatBlock", level);
  }

  function insertLink() {
    const url = window.prompt("Havola URL manzili:");
    if (url) exec("createLink", url);
  }

  function insertFormula() {
    editorRef.current?.focus();
    const selection = window.getSelection();
    const selectedText = selection && selection.rangeCount > 0 ? selection.toString() : "";
    document.execCommand("insertText", false, selectedText ? `$${selectedText}$` : "$F = ma$");
    handleInput();
  }

  return (
    <div className="rounded-md border border-border">
      <div className={`flex flex-wrap gap-1 border-b border-border bg-primary/5 p-1.5 ${disabled ? "pointer-events-none opacity-50" : ""}`} role="toolbar" aria-label="Matn formatlash">
        {TOOLBAR_BUTTONS.map((btn) => (
          <button
            key={btn.command}
            type="button"
            title={btn.title}
            aria-label={btn.title}
            onClick={() => exec(btn.command)}
            className="rounded px-2 py-1 text-sm font-medium text-foreground hover:bg-primary/10"
          >
            {btn.label}
          </button>
        ))}
        <span className="mx-1 w-px bg-border" />
        <button type="button" title="Sarlavha 2" aria-label="Sarlavha 2" onClick={() => insertHeading("h2")} className="rounded px-2 py-1 text-sm font-medium text-foreground hover:bg-primary/10">H2</button>
        <button type="button" title="Sarlavha 3" aria-label="Sarlavha 3" onClick={() => insertHeading("h3")} className="rounded px-2 py-1 text-sm font-medium text-foreground hover:bg-primary/10">H3</button>
        <span className="mx-1 w-px bg-border" />
        <button type="button" title="Raqamlangan ro'yxat" aria-label="Raqamlangan ro'yxat" onClick={() => exec("insertOrderedList")} className="rounded px-2 py-1 text-sm text-foreground hover:bg-primary/10">1.</button>
        <button type="button" title="Belgili ro'yxat" aria-label="Belgili ro'yxat" onClick={() => exec("insertUnorderedList")} className="rounded px-2 py-1 text-sm text-foreground hover:bg-primary/10">•</button>
        <button type="button" title="Havola" aria-label="Havola" onClick={insertLink} className="rounded px-2 py-1 text-sm text-foreground hover:bg-primary/10">🔗</button>
        <span className="mx-1 w-px bg-border" />
        <button type="button" title="Formula (LaTeX)" aria-label="Formula qo'shish" onClick={insertFormula} className="rounded px-2 py-1 text-sm text-foreground hover:bg-primary/10">∑ Formula</button>
        <span className="mx-1 w-px bg-border" />
        <button type="button" title="Bekor qilish" aria-label="Bekor qilish" onClick={() => exec("undo")} className="rounded px-2 py-1 text-sm text-foreground hover:bg-primary/10">↺</button>
        <button type="button" title="Qaytarish" aria-label="Qaytarish" onClick={() => exec("redo")} className="rounded px-2 py-1 text-sm text-foreground hover:bg-primary/10">↻</button>
      </div>
      <div
        ref={editorRef}
        contentEditable={!disabled}
        role="textbox"
        aria-multiline="true"
        aria-label={ariaLabel}
        onInput={handleInput}
        onPaste={(e) => {
          // Plain-text paste only — prevents pasting arbitrary rich
          // HTML (e.g. from a webpage) that could contain tags/
          // attributes outside this toolbar's own output. The backend
          // sanitizer is still the real boundary; this is defense in
          // depth at the authoring UX layer.
          e.preventDefault();
          const text = e.clipboardData.getData("text/plain");
          document.execCommand("insertText", false, text);
        }}
        data-placeholder={placeholder}
        className={`${minHeightClassName} overflow-y-auto p-3 text-sm text-foreground outline-none empty:before:text-foreground/40 empty:before:content-[attr(data-placeholder)]`}
      />
    </div>
  );
}
