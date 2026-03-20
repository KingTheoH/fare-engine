import { spawn } from 'child_process'
import path from 'path'
import type { FlightConnector } from './base'
import type { FlightOffer, SearchSpec } from '../lib/types'

function runAmadeus(input: object): Promise<FlightOffer[]> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'scripts', 'amadeus_fetcher.py')
    const proc = spawn('python3', [scriptPath])
    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (stderr) console.error('[amadeus stderr]', stderr.trim())
      if (code !== 0) return reject(new Error(`amadeus_fetcher exited ${code}: ${stderr.slice(0, 200)}`))
      try {
        resolve(JSON.parse(stdout || '[]'))
      } catch {
        reject(new Error(`amadeus_fetcher invalid JSON: ${stdout.slice(0, 200)}`))
      }
    })

    proc.stdin.write(JSON.stringify(input))
    proc.stdin.end()
  })
}

export const amadeusConnector: FlightConnector = {
  name: 'amadeus',

  async search(spec: SearchSpec, apiKey: string): Promise<FlightOffer[]> {
    // apiKey format: "KEY:SECRET" — split on colon
    const [key, secret] = apiKey.split(':')
    if (!key || !secret) {
      console.error('[amadeusConnector] key must be in format KEY:SECRET')
      return []
    }

    const input = {
      api_key:     key,
      api_secret:  secret,
      origin:      spec.origin,
      destination: spec.destination,
      date_out:    spec.date_out,
      date_back:   spec.date_back,
      passengers:  spec.passengers,
      max_stops:   spec.max_stops,
      currency:    spec.currency,
    }

    try {
      return await runAmadeus(input)
    } catch (e) {
      console.error('[amadeusConnector] error:', e)
      return []
    }
  },
}
