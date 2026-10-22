"use client";

import Link from "next/link";
import { useAccount } from "@/components/AccountProvider";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { roleDestination } from "@/lib/auth";

export function PublicHeader({ simple = false }: { simple?: boolean }) {
  const { locale } = useI18n();
  const copy = publicCopy(locale);
  const { user } = useAccount();
  return <header className="public-header">
    <Link href="/" className="public-brand" aria-label="Coursework home"><span>CW</span>Coursework<span className="brand-period" aria-hidden="true">.</span></Link>
    <nav aria-label="Main navigation">
      {!simple ? <a href="/#how-it-works" className="public-text-link">{copy.explore}</a> : null}
      {user ? <Link href={roleDestination(user)} className="public-button public-button--small">{copy.workspace}</Link> : <><Link href="/login" className="public-text-link">{copy.login}</Link>{!simple ? <Link href="/register" className="public-button public-button--small">{copy.start}</Link> : null}</>}
    </nav>
  </header>;
}
