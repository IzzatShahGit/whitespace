import { Logo } from "@/components/brand/logo";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="relative flex flex-1 flex-col items-center justify-center gap-10 overflow-hidden px-6 py-16">
      <div className="pointer-events-none absolute left-1/2 top-1/3 h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-ember/10 blur-[120px]" />
      <Logo />
      {children}
    </div>
  );
}
