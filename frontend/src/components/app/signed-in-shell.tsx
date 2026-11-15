"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { type ReactNode, Suspense, useEffect, useState } from "react";

import { AppHeader } from "@/components/app/app-header";
import { Loading } from "@/components/views/states";
import { ApiError, useMe } from "@/lib/api/queries";

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        // Retry network blips and server errors, never "not found" or "not allowed".
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  });
}

function SessionGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const me = useMe();
  const signedOut = me.error instanceof ApiError && me.error.status === 401;

  useEffect(() => {
    if (signedOut) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [signedOut, pathname, router]);

  if (!me.data) {
    return (
      <Loading
        label={me.isError && !signedOut ? "Couldn't reach Whitespace. Please refresh." : undefined}
      />
    );
  }
  return (
    <>
      <AppHeader user={me.data} />
      {children}
    </>
  );
}

/**
 * Everything behind sign-in: data cache, session check, header.
 * Rendered in the browser; the Suspense boundary lets the URL-reading hooks
 * (pathname, search params) work on routes whose params are only known at request time.
 */
export function SignedInShell({ children }: { children: ReactNode }) {
  const [client] = useState(makeClient);
  return (
    <QueryClientProvider client={client}>
      <Suspense fallback={<Loading />}>
        <SessionGate>{children}</SessionGate>
      </Suspense>
    </QueryClientProvider>
  );
}
