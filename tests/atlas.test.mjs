import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { ATLAS, ANIMATIONS, STATUSES, lookFrame } from '../companion/animations.js';

test('shipped sprite retains verified source bytes and dimensions', () => {
  const png = readFileSync(new URL('../companion/assets/jonah.png', import.meta.url));
  assert.equal(createHash('sha256').update(png).digest('hex'), '828b0fb468382f37aaf0d62a3e86cb33e5fcad5dbde8aeb091d6778b32a77790');
  assert.equal(png.readUInt32BE(16), ATLAS.width);
  assert.equal(png.readUInt32BE(20), ATLAS.height);
  assert.equal(png[25], 6, 'RGBA PNG');
  assert.equal(ATLAS.columns * ATLAS.cellWidth, ATLAS.width);
  assert.equal(ATLAS.rows * ATLAS.cellHeight, ATLAS.height);
});
test('all required animation frames are mapped, without using empty cells', () => {
  assert.equal(Object.keys(ANIMATIONS).length, 9);
  assert.equal(Object.values(ANIMATIONS).reduce((n, a) => n + a.durations.length, 0), 57);
  const rows = Object.values(ANIMATIONS).map(a => a.row);
  assert.deepEqual(rows, [0,1,2,3,4,5,6,7,8]);
  assert.deepEqual(Object.values(ANIMATIONS).map(a => a.durations.length), [6,8,8,4,5,8,6,6,6]);
  for (const a of Object.values(ANIMATIONS)) assert(a.durations.every(ms => ms > 0));
  for (const status of Object.values(STATUSES)) assert(Object.hasOwn(ANIMATIONS, status.animation));
});
test('16 directions and negative/wrapped angles use the verified look rows', () => {
  const cells = Array.from({ length: 16 }, (_, i) => lookFrame(i * 22.5));
  assert.equal(new Set(cells.map(c => `${c.row}:${c.column}`)).size, 16);
  assert.deepEqual(lookFrame(0), { row: 9, column: 0 });
  assert.deepEqual(lookFrame(90), { row: 9, column: 4 });
  assert.deepEqual(lookFrame(180), { row: 10, column: 0 });
  assert.deepEqual(lookFrame(270), { row: 10, column: 4 });
  assert.deepEqual(lookFrame(-90), lookFrame(270));
  assert.deepEqual(lookFrame(360), lookFrame(0));
  assert.throws(() => lookFrame(NaN)); assert.throws(() => lookFrame(Infinity));
});
