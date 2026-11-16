import { SettingsNav } from "@/components/settings/settings-nav";
import { Page, PageHeader } from "@/components/ui/card";

export default function SettingsLayout({ children }: LayoutProps<"/app/settings">) {
  return (
    <Page>
      <PageHeader
        title="Settings"
        description="Your account, your business, and how Whitespace looks."
      />
      <div className="grid gap-6 lg:grid-cols-[12rem_1fr]">
        <SettingsNav />
        <div className="flex min-w-0 flex-col gap-6">{children}</div>
      </div>
    </Page>
  );
}
