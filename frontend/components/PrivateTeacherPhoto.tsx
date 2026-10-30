"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { authFetch } from "@/lib/auth";

/** Fetch private images as blobs: credentialed cross-origin requests, no public URL. */
export function PrivateTeacherPhoto({ version, path = "/api/auth/avatar", name }: { version: string | null; path?: string; name: string }) {
  const [source, setSource] = useState<{ url: string; version: string; path: string } | null>(null);
  useEffect(() => {
    if (!version) return;
    const controller = new AbortController(); let url = "";
    void authFetch(path, { signal: controller.signal }).then(async response => {
      if (!response.ok) return;
      const data = await response.blob();
      if (!controller.signal.aborted) { url = URL.createObjectURL(data); setSource({ url, version, path }); }
    }).catch(() => {});
    return () => { controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [version, path]);
  return version && source?.version === version && source.path === path ? <Image unoptimized className="teacher-photo" width={88} height={88} src={source.url} alt={name} /> : <span className="teacher-photo teacher-photo--initial" aria-label={name}>{name.trim().slice(0, 1).toLocaleUpperCase()}</span>;
}
