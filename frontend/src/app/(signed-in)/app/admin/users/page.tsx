import type { Metadata } from "next";
import { Suspense } from "react";

import { UsersView } from "@/components/admin/users-view";

// Renders after the session check: see (signed-in)/layout.tsx.
export const instant = false;

export const metadata: Metadata = { title: "Users · Admin · Whitespace" };

export default function AdminUsersPage() {
  // Reads ?segment=, ?status=, ?sort=, ?q= and ?page= from the URL.
  return (
    <Suspense>
      <UsersView />
    </Suspense>
  );
}
