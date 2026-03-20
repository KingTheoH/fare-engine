'use client'
import { useEffect, useState } from 'react'

interface Settings {
  kiwi_api_key: string
  serpapi_key: string
  home_airport: string
  default_passengers: number
  currency: string
}

export default function SettingsPage() {
  const [form, setForm] = useState<Settings>({
    kiwi_api_key: '', serpapi_key: '', home_airport: '',
    default_passengers: 1, currency: 'USD',
  })
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/settings').then(r => r.json()).then(d => {
      setForm(d)
      setLoading(false)
    })
  }, [])

  async function save() {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  if (loading) return <div className="text-zinc-500 text-sm">Loading…</div>

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-white mb-6">⚙️ Settings</h1>

      <div className="space-y-6">
        {/* API Keys */}
        <section>
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide mb-3">API Keys</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                RapidAPI Key{' '}
                <span className="text-zinc-600">(Sky Scrapper — Skyscanner data)</span>{' '}
                <a href="https://rapidapi.com/apiheya/api/sky-scrapper" target="_blank" rel="noopener" className="text-zinc-500 underline">
                  Get free key ↗
                </a>
              </label>
              <input
                type="password"
                value={form.kiwi_api_key}
                onChange={e => setForm(f => ({ ...f, kiwi_api_key: e.target.value }))}
                placeholder="yourApiKey:yourApiSecret"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 text-sm focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                SerpApi Key{' '}
                <a href="https://serpapi.com" target="_blank" rel="noopener" className="text-zinc-500 underline">
                  Get free key (100/mo) ↗
                </a>
              </label>
              <input
                type="password"
                value={form.serpapi_key}
                onChange={e => setForm(f => ({ ...f, serpapi_key: e.target.value }))}
                placeholder="Your SerpApi key"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 text-sm focus:outline-none focus:border-zinc-500"
              />
            </div>
          </div>
        </section>

        {/* Preferences */}
        <section>
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide mb-3">Preferences</h2>
          <div className="space-y-3">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Home Airport (IATA)</label>
              <input
                type="text"
                value={form.home_airport}
                onChange={e => setForm(f => ({ ...f, home_airport: e.target.value.toUpperCase() }))}
                placeholder="e.g. JFK"
                maxLength={3}
                className="w-32 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 text-sm font-mono focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Default Passengers</label>
              <input
                type="number"
                min={1}
                max={9}
                value={form.default_passengers}
                onChange={e => setForm(f => ({ ...f, default_passengers: Number(e.target.value) }))}
                className="w-20 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 text-sm focus:outline-none focus:border-zinc-500"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">Currency</label>
              <select
                value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 text-sm focus:outline-none focus:border-zinc-500"
              >
                {['USD', 'EUR', 'GBP', 'JPY', 'AUD'].map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
        </section>

        <button
          onClick={save}
          className="px-6 py-2.5 bg-white text-zinc-900 rounded-lg text-sm font-medium hover:bg-zinc-100 transition-colors"
        >
          {saved ? '✓ Saved' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}
