export interface QueueHandlerContext<T> {
  data: T
}

export type QueueEvent = 'enqueue' | 'dequeue' | 'drain' | 'error'

export function createQueue<T>(options: {
  handlers: Array<(ctx: QueueHandlerContext<T>) => Promise<void>>
}) {
  const queue: T[] = []
  const listeners = new Map<QueueEvent, Array<(...args: unknown[]) => void>>()
  let draining = false

  function on(event: QueueEvent, listener: (...args: unknown[]) => void) {
    const current = listeners.get(event) ?? []
    current.push(listener)
    listeners.set(event, current)
  }

  function emit(event: QueueEvent, ...args: unknown[]) {
    for (const listener of listeners.get(event) ?? [])
      listener(...args)
  }

  async function drain() {
    if (draining)
      return
    draining = true
    try {
      while (queue.length > 0) {
        const payload = queue.shift() as T
        emit('dequeue', payload, queue.length)
        for (const handler of options.handlers) {
          try {
            await handler({ data: payload })
          }
          catch (error) {
            emit('error', payload, error)
          }
        }
      }
      emit('drain')
    }
    finally {
      draining = false
    }
  }

  function enqueue(payload: T) {
    queue.push(payload)
    emit('enqueue', payload, queue.length)
    void drain()
  }

  function clear() {
    queue.length = 0
  }

  function length() {
    return queue.length
  }

  return { enqueue, clear, length, on }
}

export type UseQueueReturn<T> = ReturnType<typeof createQueue<T>>
