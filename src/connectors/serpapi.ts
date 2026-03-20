import { spawn } from 'child_process'
import path from 'path'
import type { FlightConnector } from './base'
import type { FlightOffer, SearchSpec } from '../lib/types'

function runSerpApi(input: object): Promise<FlightOffer[]> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'scripts', 'serpapi_fetcher.py')
    const proc = spawn('python3', [scriptPath])
    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (stderr) console.error('[serpapi stderr]', stderr.trim())
      if (code !== 0) return reject(new Error(`serpapi_fetcher exited ${code}: ${stderr.slice(0, 200)}`))
      try {
        resolve(JSON.parse(stdout || '[]'))
      } catch {
        reject(new Error(`serpapi_fetcher invalid JSON: ${stdout.slice(0, 200)}`))
      }
    })

    proc.stdin.write(JSON.stringify(input))
    proc.stdin.end()
  })
}

export const serpapiConnector: FlightConnector = {
  name: 'serpapi',

  async search(spec: SearchSpec, apiKey: string): Promise<FlightOffer[]> {
    const input = {
      departure_id: spec.origin,
      arrival_id: spec.destination,
      outbound_date: spec.date_out,
      return_date: spec.date_back,
      flight_type: spec.date_back ? 1 : 2,
      currency: spec.currency,
      api_key: apiKey,
    }

    try {
      return await runSerpApi(input)
    } catch (e) {
      console.error('[serpapiConnector] error:', e)
      return []
    }
  },
}
