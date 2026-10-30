import { Noto_Sans_SC, Noto_Sans_TC } from "next/font/google";

// Keep the large Unicode-range face sheets out of the English route's critical
// CSS. The server imports this module only for a Chinese interface locale.
const simplified = Noto_Sans_SC({ variable: "--font-public-sc", display: "swap", preload: false });
const traditional = Noto_Sans_TC({ variable: "--font-public-tc", display: "swap", preload: false });
export const publicChineseClass = { "zh-CN": simplified.variable, "zh-HK": traditional.variable };
