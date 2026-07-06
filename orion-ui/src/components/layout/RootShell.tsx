"use client";

import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

interface RootShellProps {
  children: React.ReactNode;
}

export function RootShell({ children }: RootShellProps) {
  return (
    <div className="flex h-screen bg-neutral-950 text-neutral-100">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
