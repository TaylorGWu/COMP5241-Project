"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

const copy = {
  en: { add: "Add slide", before: "Before current slide", after: "After current slide", edit: "Edit slide", remove: "Delete slide", confirm: "Delete this slide?", hint: "This removes the slide and its lesson-plan references. Other slides are kept.", cancel: "Cancel" },
  "zh-HK": { add: "新增幻燈片", before: "在目前頁前新增", after: "在目前頁後新增", edit: "編輯幻燈片", remove: "刪除幻燈片", confirm: "刪除這頁幻燈片？", hint: "這頁及其教案引用將被移除，其他幻燈片會保留。", cancel: "取消" },
  "zh-CN": { add: "新增幻灯片", before: "在当前页前新增", after: "在当前页后新增", edit: "编辑幻灯片", remove: "删除幻灯片", confirm: "删除这页幻灯片？", hint: "这页及其教案引用将被移除，其他幻灯片会保留。", cancel: "取消" },
};

export function SlideActions({ busy, editing, slideId, title, onInsert, onEdit, onDelete }: {
  busy: boolean; editing: boolean; slideId?: string; title?: string;
  onInsert: (position: "before" | "after") => void;
  onEdit: () => void; onDelete: () => Promise<unknown>;
}) {
  const { locale } = useI18n();
  const t = copy[locale];
  const [open, setOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => { if (!menu.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return <div className="slide-actions" data-slide-actions>
    <div ref={menu} className="slide-actions__insert" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }} onKeyDown={(event) => {
      if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); }
    }}>
      <button ref={trigger} type="button" className="slide-actions__add" disabled={busy || editing}
        aria-expanded={open} aria-controls="slide-insert-options" onClick={() => {
          if (!slideId) onInsert("after"); else setOpen(!open);
        }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>{t.add}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m7 10 5 5 5-5" /></svg>
      </button>
      {open ? <div id="slide-insert-options" className="slide-actions__options">
        <button type="button" onClick={() => { setOpen(false); onInsert("before"); }}>{t.before}</button>
        <button type="button" onClick={() => { setOpen(false); onInsert("after"); }}>{t.after}</button>
      </div> : null}
    </div>
    <Button variant="quiet" disabled={busy || editing || !slideId} onClick={onEdit}>{t.edit}</Button>
    <Button variant="quiet" className="slide-actions__delete" disabled={busy || editing || !slideId} onClick={() => dialog.current?.showModal()}>{t.remove}</Button>
    <dialog ref={dialog} className="slide-delete-dialog" aria-labelledby="slide-delete-title" onCancel={(event) => { if (busy) event.preventDefault(); }}>
      <h2 id="slide-delete-title">{t.confirm}</h2><p className="slide-delete-dialog__name">{title}</p><p>{t.hint}</p>
      <div className="slide-delete-dialog__buttons">
        <Button autoFocus disabled={busy} onClick={() => dialog.current?.close()}>{t.cancel}</Button>
        <Button className="slide-actions__delete" disabled={busy} onClick={async () => { await onDelete(); dialog.current?.close(); }}>{t.remove}</Button>
      </div>
    </dialog>
  </div>;
}
