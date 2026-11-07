"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { CourseWorkflowDemo } from "@/components/CourseWorkflowDemo";
import { PublicHeader } from "@/components/PublicHeader";
import { useI18n } from "@/lib/i18n";
import { homepageCopy } from "@/lib/homepage-copy";
import { useAccount } from "@/components/AccountProvider";
import { roleDestination } from "@/lib/auth";

export function PublicHome() {
  const { locale } = useI18n();
  const c = homepageCopy(locale);
  const { user } = useAccount();
  return <main className="public-page public-home-page">
    <a className="home-skip" href="#home-main">{locale === "en" ? "Skip to content" : locale === "zh-HK" ? "跳至主要內容" : "跳至主要内容"}</a>
    <PublicHeader />
    <section className="public-hero" id="home-main" aria-labelledby="home-title">
      <div className="public-hero-copy"><h1 id="home-title">{c.headline.map((line, index) => <span key={line}>{line}{index < c.headline.length - 1 ? " " : null}</span>)}</h1>
        <p>{c.body}</p>
        <Link className="public-button home-primary-action" href={user ? roleDestination(user) : "/register/instructor"}>{user ? (locale === "en" ? "Open workspace" : locale === "zh-HK" ? "進入後台" : "进入后台") : c.create}<Arrow /></Link>
        <div className="home-assurance"><Check /><span>{c.assurance}</span></div>
      </div>
      <CourseWorkflowDemo hero />
    </section>
    <section className="home-overview" id="home-workflow" aria-labelledby="home-overview-title"><div className="home-section-inner"><h2 id="home-overview-title">{c.overview}</h2><ol>{c.steps.map((step,index)=><li key={step.title}><span className="home-step-icon" aria-hidden="true">{index===0?<Document />:index===1?<Chapters />:<Adjust />}</span><div><h3>{index+1}. {step.title}</h3><p>{step.body}</p></div>{index<2?<span className="home-step-arrow" aria-hidden="true"><Arrow /></span>:null}</li>)}</ol></div></section>
    <Tagline lines={c.tagline} detail={c.detail} />
    <section className="home-faq" aria-labelledby="home-faq-title"><h2 id="home-faq-title">{c.faqTitle}</h2><div>{c.faq.map(item=><details key={item.question}><summary>{item.question}<span aria-hidden="true">+</span></summary><p>{item.answer}</p></details>)}</div></section>
    <section className="home-close"><h2>{c.close}</h2><Link className="public-button" href={user ? roleDestination(user) : "/register/instructor"}>{user ? (locale === "en" ? "Open workspace" : locale === "zh-HK" ? "進入後台" : "进入后台") : c.create}<Arrow /></Link><p>{c.student} <Link href="/register/student">{c.studentLink}</Link></p></section>
  </main>;
}

function Tagline({ lines, detail }: { lines: string[]; detail: string }) {
  const host = useRef<HTMLElement>(null);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.setAttribute("data-revealed", "true"); observer.unobserve(entry.target); } }), { threshold: .6 });
    host.current?.querySelectorAll("[data-reveal-word]").forEach(word => observer.observe(word));
    return () => observer.disconnect();
  }, [lines]);
  return <section className="home-tagline" ref={host}><h2 aria-label={lines.join(" ")}>{lines.map(line=><span className="home-tagline-line" key={line}>{line.split(" ").map((word,index)=><span key={`${word}-${index}`} data-reveal-word style={{transitionDelay:`${Math.min(index*60,400)}ms`}}>{word}{" "}</span>)}</span>)}</h2><p>{detail}</p></section>;
}

export function Arrow() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h14m-6-6 6 6-6 6" /></svg>; }
export function Document() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6M8 13h8m-8 4h5" /></svg>; }
export function Check() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6" /></svg>; }
function Chapters() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M9 6h11M9 12h11M9 18h11M3 6h1M3 12h1M3 18h1" /></svg>; }
function Adjust() { return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M3 6h10m4 0h4M3 18h4m4 0h10M3 12h4m4 0h10" /><circle cx="15" cy="6" r="2" /><circle cx="9" cy="12" r="2" /><circle cx="9" cy="18" r="2" /></svg>; }
