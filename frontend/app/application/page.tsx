import { ApplicationPage } from "@/components/AccountPages";
import { AccountGate } from "@/components/AccountProvider";
export default function Page() { return <AccountGate destination="/application"><ApplicationPage /></AccountGate>; }
