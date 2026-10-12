import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { cookies } from "next/headers";

// ⚠️ 只从 i18n-config 取纯函数/常量 —— i18n.tsx 是 "use client" 模块,
//    服务端 import 它拿到的是客户端引用,调用会 500。
import { I18nProvider } from "@/lib/i18n";
import { LOCALE_COOKIE, normalizeLocale } from "@/lib/i18n-config";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PathPilot · Course studio",
  description: "Draft course material with AI, then review it before it reaches students.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // 语言存在 cookie 里,服务端直接读出来。
  // 这样首屏就是正确语言 —— 不用等 JS 再切一次,也就不会闪。
  // 代价是路由变成动态渲染,对一个要连后端的应用来说无所谓。
  const store = await cookies();
  const locale = normalizeLocale(store.get(LOCALE_COOKIE)?.value);

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <I18nProvider initialLocale={locale}>{children}</I18nProvider>
      </body>
    </html>
  );
}
