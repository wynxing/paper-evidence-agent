import type { TaskStatus } from '../api/contracts.ts'
import { isTerminal } from './model.ts'

/** Production poll spacing. Tests inject a shorter interval. */
export const POLL_INTERVAL_MS = 1500
/** A generation token prevents stopped/hidden-page requests publishing late data. */
export function createPoller<T extends { status: TaskStatus }>(read: (signal: AbortSignal) => Promise<T>, receive: (value: T) => void, fail: (error: unknown) => void, interval = POLL_INTERVAL_MS) {
  let generation = 0; let timer: ReturnType<typeof setTimeout> | undefined; let controller: AbortController | undefined
  function stop() { generation++; clearTimeout(timer); controller?.abort() }
  function start() {
    stop(); const current = generation
    async function tick() {
      controller = new AbortController()
      try {
        const value = await read(controller.signal)
        if (current !== generation) return
        receive(value)
        if (isTerminal(value.status)) return
      } catch (error) { if (current !== generation) return; fail(error) }
      if (current === generation) timer = setTimeout(tick, interval)
    }
    void tick()
  }
  return { start, stop }
}
