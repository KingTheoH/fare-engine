import { spawn } from 'child_process'
import path from 'path'
import type { FlightConnector } from './base'
import type { FlightOffer, SearchSpec } from '../lib/types'

// Common throwaway cities for fuel dump detection
const THROWAWAY_CANDIDATES: Record<string, string[]> = {
  'FCO': ['DUB', 'LIS', 'AMS'],
  'LHR': ['DUB', 'CPH', 'AMS'],
  'CDG': ['DUB', 'LIS', 'VIE'],
  'FRA': ['DUB', 'CPH', 'LIS'],
  'AMS': ['DUB', 'LIS', 'CPH'],
  'NRT': ['HKG', 'BKK', 'KUL'],
  'SIN': ['BKK', 'KUL', 'CGK'],
}

function runKiwi(input: object): Promise<FlightOffer[]> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'scripts', 'kiwi_fetcher.py')
    const proc = spawn('python3', [scriptPath])
    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (stderr) console.error('[kiwi stderr]', stderr.trim())
      if (code !== 0) return reject(new Error(`kiwi_fetcher exited ${code}: ${stderr.slice(0, 200)}`))
      try {
        resolve(JSON.parse(stdout || '[]'))
      } catch {
        reject(new Error(`kiwi_fetcher invalid JSON: ${stdout.slice(0, 200)}`))
      }
    })

    proc.stdin.write(JSON.stringify(input))
    proc.stdin.end()
  })
}

export const kiwiConnector: FlightConnector = {
  name: 'kiwi',

  async search(spec: SearchSpec, apiKey: string): Promise<FlightOffer[]> {
    const throwawayDests = THROWAWAY_CANDIDATES[spec.destination] || []

    const input = {
      fly_from: spec.origin,
      fly_to: spec.destination,
      date_from: spec.date_out,
      date_to: spec.date_out,
      flight_type: spec.date_back ? 'round' : 'oneway',
      max_stopovers: spec.max_stops,
      curr: spec.currency,
      throwaway_dests: throwawayDests,
      api_key: apiKey,
    }

    try {
      return await runKiwi(input)
    } catch (e) {
      console.error('[kiwiConnector] error:', e)
      return []
    }
  },
}
