"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut } from "next-auth/react";
import { Button } from "@/components/ui/button";
import { LogOut, Search, Activity } from "lucide-react";

const navLinks = [
  { href: "/dashboard", label: "Search", icon: Search },
  { href: "/dashboard/health", label: "Scraper Health", icon: Activity },
];

export function Nav({ children }: { children?: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b bg-background">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/dashboard"
            className="text-lg font-semibold tracking-tight"
          >
            Procurement Intelligence
          </Link>
          <div className="flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive =
                link.href === "/dashboard"
                  ? pathname === "/dashboard"
                  : pathname.startsWith(link.href);
              const Icon = link.icon;
              return (
                <Link key={link.href} href={link.href}>
                  <Button
                    variant={isActive ? "secondary" : "ghost"}
                    size="sm"
                    className="gap-2"
                  >
                    <Icon className="h-4 w-4" />
                    {link.label}
                  </Button>
                </Link>
              );
            })}
          </div>
        </div>
        <div className="flex items-center gap-4">
          {children}
          <Button
            variant="ghost"
            size="sm"
            className="gap-2"
            onClick={() => signOut({ callbackUrl: "/login" })}
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </div>
    </nav>
  );
}
