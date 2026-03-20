import { spawn } from 'child_process'
import path from 'path'
import type { FlightConnector } from './base'
import type { FlightOffer, SearchSpec } from '../lib/types'

function runSkyScrapper(input: object): Promise<FlightOffer[]> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'scripts', 'skyscrapper_fetcher.py')
    const proc = spawn('python3', [scriptPath])
    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (stderr) console.error('[skyscrapper stderr]', stderr.trim())
      if (code !== 0) return reject(new Error(`skyscrapper_fetcher exited ${code}: ${stderr.slice(0, 200)}`))
      try {
        resolve(JSON.parse(stdout || '[]'))
      } catch {
        reject(new Error(`skyscrapper_fetcher invalid JSON: ${stdout.slice(0, 200)}`))
      }
    })

    proc.stdin.write(JSON.stringify(input))
    proc.stdin.end()
  })
}

export const skyScrapperConnector: FlightConnector = {
  name: 'skyscrapper',

  async search(spec: SearchSpec, apiKey: string): Promise<FlightOffer[]> {
    if (!apiKey) return []
    const input = {
      api_key:     apiKey,
      origin:      spec.origin,
      destination: spec.destination,
      date_out:    spec.date_out,
      date_back:   spec.date_back,
      passengers:  spec.passengers,
      cabin:       'economy',
    }
    try {
      return await runSkyScrapper(input)
    } catch (e) {
      console.error('[skyScrapperConnector] error:', e)
      return []
    }
  },
}
