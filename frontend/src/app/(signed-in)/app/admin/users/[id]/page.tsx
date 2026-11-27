import type { Metadata } from "next";

import { UserDetailView } from "@/components/admin/user-detail-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "User · Admin · Whitespace" };

export default function AdminUserPage({ params }: PageProps<"/app/admin/users/[id]">) {
  return <UserDetailView params={params} />;
}
