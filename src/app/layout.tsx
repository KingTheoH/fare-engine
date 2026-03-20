import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import Link from 'next/link'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'Cheap Flight Finder',
  description: 'Fuel dump, hidden city & YQ-free deal detector',
}

const NAV = [
  { href: '/', label: '🔍 Search' },
  { href: '/saved', label: '🔖 Saved' },
  { href: '/history', label: '🕐 History' },
  { href: '/settings', label: '⚙️ Settings' },
]

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="bg-zinc-950 text-zinc-100 font-[var(--font-inter)] min-h-screen flex">
        {/* Sidebar */}
        <aside className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-900 flex flex-col py-6 px-4 fixed h-full">
          <div className="mb-8">
            <div className="text-lg font-bold text-white">🛫 Cheap Flights</div>
            <div className="text-xs text-zinc-500 mt-0.5">Loophole detector</div>
          </div>
          <nav className="flex flex-col gap-1">
            {NAV.map(n => (
              <Link
                key={n.href}
                href={n.href}
                className="px-3 py-2 rounded-lg text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-colors"
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto text-xs text-zinc-600 leading-relaxed">
            Finds deals via Kiwi + SerpApi. Does not book flights.
          </div>
        </aside>

        {/* Main */}
        <main className="ml-56 flex-1 min-h-screen p-8">
          {children}
        </main>
      </body>
    </html>
  )
}
