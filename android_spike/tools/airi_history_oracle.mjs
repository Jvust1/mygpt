// Executes the exact pinned AIRI source, without npm, downloads or runtime code edits.
import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { resolve, dirname } from 'node:path'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const source = resolve(root, 'third_party/airi/reference/compaction.ts')
const fixture = resolve(root, 'android_spike/src/test/resources/airi-history-golden.json')
const blob = data => createHash('sha1').update(Buffer.from(`blob ${data.length}\0`)).update(data).digest('hex')
if (blob(readFileSync(source)) !== '59a76a9877086f66b5abc09b0f22802e4e27df7d') throw Error('AIRI source identity mismatch')
if (blob(readFileSync(resolve(root, 'third_party/airi/LICENSE'))) !== '1bd715572472cd766a5c1444a467f5f011b14aaa') throw Error('AIRI license identity mismatch')
const { compactConversationEntries } = await import(pathToFileURL(source))
const cases = []
for (let i = 0; i < 128; i++) {
  const roles = []
  const groups = 2 + i % 7
  if (i % 3 === 0) roles.push('assistant')
  for (let group = 0; group < groups; group++) {
    roles.push('user')
    for (let j = 0; j < (i + group) % 4; j++) roles.push('assistant')
  }
  const limit = 1 + i % (groups - 1)
  const items = roles.map((role, index) => role === 'user'
    ? { type: 'turn', turnType: 'chat', turnIndex: index, actor: 'player', action: { kind: 'text', text: `m${index}` }, id: index }
    : { type: 'reaction', reactionType: 'assistant-chat', text: `m${index}`, id: index })
  const entries = [{ id: 'history', role: 'user', segments: [{ type: 'history-block', compacted: false, items }] }]
  const kept = compactConversationEntries({ entries, recentTurnLimit: limit })[0].segments[0].items
    .filter(item => item.type !== 'summary').map(item => item.id)
  cases.push({ id: `airi-${i}`, roles, limit, kept_indices: kept })
}
const expected = { source_commit: 'b40e3e87b149ea5fb75d4944440493829e601411', cases }
if (process.argv.includes('--write')) writeFileSync(fixture, JSON.stringify(expected, null, 2) + '\n')
if (JSON.stringify(JSON.parse(readFileSync(fixture, 'utf8'))) !== JSON.stringify(expected)) throw Error('AIRI Android history fixture mismatch')
console.log(`Actual AIRI history oracle PASS: ${cases.length} Android cases`)
