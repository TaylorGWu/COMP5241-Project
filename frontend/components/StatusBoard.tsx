"use client";

import type { StatusGroup, StatusState } from "@/lib/api";
import { inputCls } from "@/components/ui";

const stateLabels: Record<StatusState, string> = {
  complete: "Complete", partial: "Partial", unverified: "To confirm", excluded: "Out of scope",
};

function StatusMark({ state }: { state: StatusState }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden className="h-5 w-5 shrink-0">
    <circle cx="12" cy="12" r="9" />
    {state === "complete" ? <path d="m7.5 12 3 3 6-6" /> : state === "partial" ? <path d="M12 7v5l3 2" /> : state === "excluded" ? <path d="M8 12h8" /> : <path d="M12 7v6m0 3v1" />}
  </svg>;
}

/** A plain IR component: no course IDs, inferred completion or model calls. */
export function StatusBoard({ groups }: { groups: StatusGroup[] }) {
  return <div data-status-board="1" className={`grid min-h-0 flex-1 gap-6 ${groups.length === 1 ? "grid-cols-1" : groups.length === 2 ? "grid-cols-2" : "grid-cols-3"}`}>
    {groups.map((group, index) => <section key={index} className="flex min-w-0 flex-col" aria-label={group.title}>
      <h4 className="mb-4 border-b border-line pb-3 text-xl font-semibold text-ink">{group.title}</h4>
      <ul className="flex min-h-0 flex-1 flex-col justify-start gap-3">
        {group.items.map((item, row) => <li key={row} data-status={item.status} className="flex items-start gap-2">
          <span className={item.status === "complete" ? "text-green" : item.status === "partial" ? "text-amber" : "text-muted"}><StatusMark state={item.status} /></span>
          <span className="min-w-0"><span className="block text-base leading-6 font-medium text-ink">{item.label}</span><span className={item.status === "complete" ? "sr-only" : "block text-xs leading-4 text-body"}>{stateLabels[item.status]}</span></span>
        </li>)}
      </ul>
    </section>)}
  </div>;
}

export function StatusBoardEditor({ groups, onChange }: { groups: StatusGroup[]; onChange: (value: StatusGroup[]) => void }) {
  const update = (index: number, value: StatusGroup) => onChange(groups.map((group, i) => i === index ? value : group));
  return <div className="grid gap-4" aria-label="Status groups">
    {groups.map((group, index) => <fieldset key={index} className="grid gap-2 rounded-lg border border-line p-4">
      <legend className="px-2 text-sm text-body">Group {index + 1}</legend>
      <input className={inputCls} aria-label={`Group ${index + 1} title`} maxLength={40} value={group.title} onChange={e => update(index, { ...group, title: e.target.value })} />
      {group.items.map((item, row) => <div key={row} className="flex flex-wrap items-center gap-2">
        <input className={`${inputCls} min-w-0 flex-1`} aria-label={`Group ${index + 1} item ${row + 1}`} maxLength={80} value={item.label} onChange={e => update(index, { ...group, items: group.items.map((old, i) => i === row ? { ...old, label: e.target.value } : old) })} />
        <select className={inputCls} aria-label={`Group ${index + 1} item ${row + 1} status`} value={item.status} onChange={e => update(index, { ...group, items: group.items.map((old, i) => i === row ? { ...old, status: e.target.value as StatusState } : old) })}>
          {Object.entries(stateLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button type="button" className="text-sm text-body underline" disabled={group.items.length === 1} onClick={() => update(index, { ...group, items: group.items.filter((_, i) => i !== row) })}>Remove item {row + 1}</button>
      </div>)}
      <div className="flex gap-4 text-sm text-blue">
        <button type="button" disabled={group.items.length >= 6} onClick={() => update(index, { ...group, items: [...group.items, { label: "New item", status: "unverified" }] })}>Add item</button>
        <button type="button" disabled={groups.length === 1} onClick={() => onChange(groups.filter((_, i) => i !== index))}>Remove group</button>
      </div>
    </fieldset>)}
    <button type="button" className="justify-self-start text-sm text-blue" disabled={groups.length >= 3} onClick={() => onChange([...groups, { title: "New group", items: [{ label: "New item", status: "unverified" }] }])}>Add group</button>
  </div>;
}
