"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAccount } from "@/components/AccountProvider";
import { useI18n } from "@/lib/i18n";
import { publicCopy } from "@/lib/public-copy";
import { AccountActions } from "@/components/AccountActions";
import { roleDestination } from "@/lib/auth";
import { homepageCopy } from "@/lib/homepage-copy";

export function PublicHeader({ simple = false }: { simple?: boolean }) {
  const { locale } = useI18n();
  const copy = publicCopy(locale);
  const { user } = useAccount();
  const pathname = usePathname();
  const home = pathname === "/";
  return <header className="public-header">
    <Link href="/" className="public-brand"><span>CW</span>Coursework<span className="brand-period" aria-hidden="true">.</span></Link>
    <nav aria-label="Main navigation">
      {home ? <Link href="#home-workflow" className="public-text-link home-how-link">{homepageCopy(locale).how}</Link> : null}
      {(!simple || pathname === "/profile") && user ? <Link href={roleDestination(user)} className="public-text-link" data-workspace-entry>{copy.dashboard}</Link> : null}
      {user ? <AccountActions /> : <><Link href={simple && pathname === "/login" ? "/" : "/login"} className="public-text-link">{simple && pathname === "/login" ? copy.home : copy.login}</Link>{!simple ? <Link href={home ? "/register/instructor" : "/register"} className="public-button public-button--small">{home ? homepageCopy(locale).create : copy.start}</Link> : null}</>}
    </nav>
  </header>;
}
