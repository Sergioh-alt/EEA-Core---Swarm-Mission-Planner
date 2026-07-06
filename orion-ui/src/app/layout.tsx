import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { RootShell } from "@/components/layout/RootShell";
import { ConnectionProvider } from "@/components/layout/ConnectionProvider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ORION GCS",
  description: "ORION Ground Control Station — Swarm Mission Control",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} antialiased`}>
        <ConnectionProvider>
          <RootShell>{children}</RootShell>
        </ConnectionProvider>
      </body>
    </html>
  );
}
