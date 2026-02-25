import { Nav } from "@/components/layout/nav";
import { Freshness } from "@/components/layout/freshness";
import { SessionWrapper } from "@/components/layout/session-wrapper";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SessionWrapper>
      <div className="min-h-screen bg-muted/30">
        <Nav>
          <Freshness />
        </Nav>
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </div>
    </SessionWrapper>
  );
}
