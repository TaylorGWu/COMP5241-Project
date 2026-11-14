import { AdminPortal } from "@/components/portals/AdminPortal";
import { AccountGate } from "@/components/AccountProvider";
export default function Page() { return <AccountGate destination="/admin"><AdminPortal /></AccountGate>; }
