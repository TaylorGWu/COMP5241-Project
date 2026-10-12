"use client";

/**
 * 界面多语言的**运行时层**(Provider + hook)。
 *
 * 词典和语言表在 `lib/i18n-config.ts` —— 那个文件没有 "use client",
 * 所以服务端组件也能直接用其中的纯函数(见那个文件顶部的说明)。
 * 这里只保留必须跑在客户端的东西。
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { CATALOG, LOCALE_COOKIE, type Locale, type Messages } from "@/lib/i18n-config";

type I18nValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  /** 当前语言的文案表。直接 `t.setup.headline` 取用。 */
  t: Messages;
};

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({
  initialLocale,
  children,
}: {
  initialLocale: Locale;
  children: ReactNode;
}) {
  // 初始值来自服务端读 cookie —— 所以首屏就是正确语言,不闪。
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    // 写 cookie 而不是 localStorage:下次请求服务端就能读到,首屏不用等 JS。
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=31536000; samesite=lax`;
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ locale, setLocale, t: CATALOG[locale] }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n() 必须放在 <I18nProvider> 里面");
  return ctx;
}
