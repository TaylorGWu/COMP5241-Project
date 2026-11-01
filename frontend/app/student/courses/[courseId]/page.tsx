import { AccountGate } from "@/components/AccountProvider";
import { StudentCourse } from "@/components/portals/StudentCourse";
export default async function Page({
  params,
}: {
  params: Promise<{ courseId: string }>;
}) {
  const { courseId } = await params;
  return (
    <AccountGate destination="/student">
      <StudentCourse key={courseId} courseId={courseId} />
    </AccountGate>
  );
}
