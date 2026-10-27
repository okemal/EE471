import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCommands, spokenNumber, encodeWav } from '../static/js/speech.js';

test('recognizes every required digit and operation', () => {
  assert.deepEqual(parseCommands('Zero One Two Three Four Five Six Seven Eight Nine Point Over Times Plus Minus Is.'),
    ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', '/', '*', '+', '-', '=']);
});

test('handles lexical phrases and normalized numeric recognition', () => {
  assert.deepEqual(parseCommands('Three, plus five is.'), ['3', '+', '5', '=']);
  assert.deepEqual(parseCommands('12.5 times 2 is'), ['1', '2', '.', '5', '*', '2', '=']);
  assert.deepEqual(parseCommands('clear change sign percent backspace'), ['Escape', 'F9', '%', 'Backspace']);
});

test('rejects unknown or empty phrases before applying commands', () => {
  for (const text of ['', 'three plus banana', 'open the calculator']) {
    assert.throws(() => parseCommands(text));
  }
});

test('reads signs, decimal points and scientific results', () => {
  assert.equal(spokenNumber('-8.5'), 'minus eight point five');
  assert.equal(spokenNumber('1e+12'), 'one times ten to the power plus one two');
});

test('microphone conversion emits mono 16 kHz 16-bit WAV', () => {
  const wav = encodeWav([new Float32Array(48000).fill(0.5)], 48000);
  const view = new DataView(wav);
  assert.equal(new TextDecoder().decode(wav.slice(0, 4)), 'RIFF');
  assert.equal(view.getUint16(22, true), 1);
  assert.equal(view.getUint32(24, true), 16000);
  assert.equal(view.getUint16(34, true), 16);
  assert.equal(view.getUint32(40, true), 32000);
  assert.equal(view.getInt16(44, true), 16384);
  assert.equal(wav.byteLength, 32044);
});
