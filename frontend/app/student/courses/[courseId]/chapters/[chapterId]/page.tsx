import { AccountGate } from "@/components/AccountProvider";
import { StudentPlayer } from "@/components/portals/StudentPlayer";
export default async function Page({
  params,
}: {
  params: Promise<{ courseId: string; chapterId: string }>;
}) {
  const { courseId, chapterId } = await params;
  return (
    <AccountGate destination="/student">
      <StudentPlayer
        key={`${courseId}/${chapterId}`}
        courseId={courseId}
        chapterId={chapterId}
      />
    </AccountGate>
  );
}
