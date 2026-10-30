import type { Metadata } from "next";
import { Geist, Geist_Mono, Manrope, Source_Sans_3 } from "next/font/google";
import { cookies } from "next/headers";

// ⚠️ 只从 i18n-config 取纯函数/常量 —— i18n.tsx 是 "use client" 模块,
//    服务端 import 它拿到的是客户端引用,调用会 500。
import { I18nProvider } from "@/lib/i18n";
import { LOCALE_COOKIE, normalizeLocale } from "@/lib/i18n-config";
import { PRODUCT_NAME } from "@/lib/brand";
import { ThemeProvider } from "@/lib/theme";
import { SystemSettings } from "@/components/SystemSettings";
import { AccountProvider } from "@/components/AccountProvider";
import "./globals.css";
import "./public.css";
import "./profile.css";
import "./public-refinement.css";
import "./workflow-demo.css";
import "./account-menu.css";
import "./homepage.css";
import "./profile-refinement.css";
import "./teacher-workspace-refinement.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// New faces are scoped to the public home/profile/application surfaces. Other
// workspaces retain Geist. Unicode subsets load only when the text needs them.
const publicDisplay = Manrope({ variable: "--font-public-display", subsets: ["latin"], display: "swap", preload: false });
const publicBody = Source_Sans_3({ variable: "--font-public-body", subsets: ["latin"], display: "swap", preload: false });

export const metadata: Metadata = {
  title: `${PRODUCT_NAME} · Good teaching, made tangible`,
  description: "Focused software engineering lessons. AI to draft, teachers to decide.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // 语言存在 cookie 里,服务端直接读出来。
  // 这样首屏就是正确语言 —— 不用等 JS 再切一次,也就不会闪。
  // 代价是路由变成动态渲染,对一个要连后端的应用来说无所谓。
  const store = await cookies();
  const locale = normalizeLocale(store.get(LOCALE_COOKIE)?.value);
  const chineseClass = locale === "en" ? "" : (await import("@/lib/public-chinese-fonts")).publicChineseClass[locale];

  return (
    <html
      lang={locale}
      className={`${geistSans.variable} ${geistMono.variable} ${publicDisplay.variable} ${publicBody.variable} ${chineseClass} h-full antialiased`}
    >
      <body className="min-h-full">
        <ThemeProvider>
          <I18nProvider initialLocale={locale}>
            <AccountProvider>
            {children}
            <SystemSettings />
            </AccountProvider>
          </I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
