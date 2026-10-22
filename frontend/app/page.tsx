import { redirect } from "next/navigation";

/** The teacher starts from courses, never from an unscoped editor. */
export default function Home() {
  redirect("/courses");
}
