import { spawn } from 'child_process'
import path from 'path'
import type { FlightConnector } from './base'
import type { FlightOffer, SearchSpec } from '../lib/types'

function runDemo(input: object): Promise<FlightOffer[]> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'scripts', 'demo_fetcher.py')
    const proc = spawn('python3', [scriptPath])
    let stdout = ''
    let stderr = ''

    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (code !== 0) return reject(new Error(`demo_fetcher exited ${code}: ${stderr}`))
      try { resolve(JSON.parse(stdout || '[]')) }
      catch { reject(new Error('demo_fetcher invalid JSON')) }
    })

    proc.stdin.write(JSON.stringify(input))
    proc.stdin.end()
  })
}

export const demoConnector: FlightConnector = {
  name: 'demo',
  async search(spec: SearchSpec): Promise<FlightOffer[]> {
    return runDemo({
      origin: spec.origin,
      destination: spec.destination,
      date_out: spec.date_out,
      date_back: spec.date_back,
    }).catch(() => [])
  },
}
