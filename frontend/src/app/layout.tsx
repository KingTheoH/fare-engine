import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Fare Engine",
  description: "Fare construction intelligence for travel agents",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white">
        <nav className="no-print border-b border-[#dadce0] bg-white sticky top-0 z-50">
          <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center gap-8">
            <Link href="/patterns" className="flex items-center gap-2 mr-4">
              <div className="w-7 h-7 rounded bg-[#1a73e8] flex items-center justify-center">
                <span className="text-white text-sm font-bold">F</span>
              </div>
              <span className="text-[#202124] text-[15px] font-medium tracking-tight">
                Fare Engine
              </span>
            </Link>
            <div className="flex gap-1">
              <NavLink href="/patterns">Patterns</NavLink>
              <NavLink href="/carriers">YQ Tracker</NavLink>
              <NavLink href="/validations">Validations</NavLink>
              <NavLink href="/airports">Origins</NavLink>
            </div>
          </div>
        </nav>
        <main className="max-w-[1400px] mx-auto px-6 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}

function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3 py-2 text-[13px] font-medium text-[#5f6368] hover:text-[#202124] hover:bg-[#f1f3f4] rounded-full transition-colors"
    >
      {children}
    </Link>
  );
}
