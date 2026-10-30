import { StudentAccountPage } from "@/components/AccountPages";
import { AccountGate } from "@/components/AccountProvider";
export default function Page() { return <AccountGate destination="/student"><StudentAccountPage /></AccountGate>; }
