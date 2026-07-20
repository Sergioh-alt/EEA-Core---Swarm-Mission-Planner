"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Plane,
  Map,
  Target,
  PlayCircle,
  AlertTriangle,
  Settings,
  BarChart3,
  Rocket,
  Layers,
  Radio,
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    href: "/",
    icon: <LayoutDashboard className="h-5 w-5" />,
  },
  {
    label: "Control",
    href: "/control",
    icon: <Radio className="h-5 w-5" />,
  },
  {
    label: "Fleet",
    href: "/fleet",
    icon: <Plane className="h-5 w-5" />,
  },
  {
    label: "Mission",
    href: "/mission",
    icon: <Target className="h-5 w-5" />,
  },
  {
    label: "Map",
    href: "/map",
    icon: <Map className="h-5 w-5" />,
  },
  {
    label: "Planning",
    href: "/planning",
    icon: <Layers className="h-5 w-5" />,
  },
  {
    label: "Deployment",
    href: "/deployment",
    icon: <Rocket className="h-5 w-5" />,
  },
  {
    label: "Replay",
    href: "/mission/replay",
    icon: <PlayCircle className="h-5 w-5" />,
  },
  {
    label: "Analytics",
    href: "/analytics",
    icon: <BarChart3 className="h-5 w-5" />,
  },
  {
    label: "Alerts",
    href: "/alerts",
    icon: <AlertTriangle className="h-5 w-5" />,
  },
  {
    label: "Settings",
    href: "/settings",
    icon: <Settings className="h-5 w-5" />,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-56 flex-col border-r border-neutral-800 bg-neutral-950">
      <div className="flex items-center gap-2 border-b border-neutral-800 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-600">
          <span className="text-sm font-bold text-white">O</span>
        </div>
        <div>
          <p className="text-sm font-semibold text-neutral-100">ORION</p>
          <p className="text-[10px] text-neutral-500 uppercase tracking-widest">
            Ground Control
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-3">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-200"
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-neutral-800 px-4 py-3">
        <p className="text-[10px] text-neutral-600 text-center">
          ORION GCS v10C.5
        </p>
      </div>
    </aside>
  );
}
