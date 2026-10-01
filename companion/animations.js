export const ATLAS = Object.freeze({ width: 1536, height: 2288, columns: 8, rows: 11, cellWidth: 192, cellHeight: 208 });

export const ANIMATIONS = Object.freeze({
  idle: { row: 0, durations: [280, 110, 110, 140, 140, 320] },
  'running-right': { row: 1, durations: [120, 120, 120, 120, 120, 120, 120, 220] },
  'running-left': { row: 2, durations: [120, 120, 120, 120, 120, 120, 120, 220] },
  waving: { row: 3, durations: [140, 140, 140, 280] },
  jumping: { row: 4, durations: [140, 140, 140, 140, 280] },
  failed: { row: 5, durations: [140, 140, 140, 140, 140, 140, 140, 240] },
  waiting: { row: 6, durations: [150, 150, 150, 150, 150, 260] },
  running: { row: 7, durations: [120, 120, 120, 120, 120, 220] },
  review: { row: 8, durations: [150, 150, 150, 150, 150, 280] }
});

export const STATUSES = Object.freeze({
  idle: { animation: 'idle', label: '安静陪伴' },
  working: { animation: 'running', label: '正在处理' },
  'needs-input': { animation: 'waiting', label: '等你回应' },
  ready: { animation: 'waving', label: '有新进展' },
  blocked: { animation: 'failed', label: '需要处理' }
});

// Screen-space angles: 0° right, 90° down, 180° left, 270° up.
export function lookFrame(degrees) {
  if (!Number.isFinite(degrees)) throw new TypeError('Look angle must be finite');
  const index = Math.round(((degrees % 360 + 360) % 360) / 22.5) % 16;
  return { row: 9 + Math.floor(index / 8), column: index % 8 };
}
