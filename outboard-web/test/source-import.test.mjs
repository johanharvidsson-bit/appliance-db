import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { sourceContentHash, validateSourceCandidate } from '../source-import.mjs'

const fixtureUrl = new URL('../data/sources/yamaha-owner-manual-library.json', import.meta.url)

test('validates the official Yamaha source candidate deterministically', async () => {
  const fixture = JSON.parse(await readFile(fixtureUrl, 'utf8'))
  const validated = validateSourceCandidate(fixture)
  assert.equal(validated.publisher, 'Yamaha Motor Co., Ltd.')
  assert.equal(validated.sourceAuthority, 1)
  assert.match(sourceContentHash(fixture), /^[a-f0-9]{64}$/)
  assert.equal(sourceContentHash(fixture), sourceContentHash({ ...fixture }))
})

test('rejects unverifiable or unsafe source candidates', () => {
  assert.throws(() => validateSourceCandidate({}), /Unsupported sourceType/)
  assert.throws(() => validateSourceCandidate({
    sourceType: 'manufacturer_webpage', title: 'x', publisher: 'x',
    sourceUrl: 'http://example.com', languageCode: 'en',
    retrievedAt: new Date().toISOString(), observedText: 'x',
  }), /HTTPS/)
})
