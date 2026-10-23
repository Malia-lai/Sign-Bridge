import { describe, it, expect } from 'vitest';
import { analyzeFingerStates, classifyHandGesture, extractLandmarksVector } from './handClassifier';
import { getSimulatedHand } from './gestureSimulator';

describe('extractLandmarksVector', () => {
  it('returns 126 zeros for no hands', () => {
    const v = extractLandmarksVector([]);
    expect(v).toHaveLength(126);
    expect(v.every((x) => x === 0)).toBe(true);
  });

  it('produces non-zero entries for a simulated hand', () => {
    const hands = getSimulatedHand('hello', 0);
    const v = extractLandmarksVector(hands);
    expect(v).toHaveLength(126);
    expect(v.some((x) => x !== 0)).toBe(true);
  });

  it('right hand occupies first 63 slots, left hand second 63', () => {
    const right = getSimulatedHand('hello', 0); // Right
    const vR = extractLandmarksVector(right);
    // wrist-relative: first landmark of right hand becomes 0,0,0
    expect(vR[0]).toBe(0);
    expect(vR[1]).toBe(0);
    expect(vR[2]).toBe(0);

    const two = getSimulatedHand('shawarma', 0); // Right + Left
    const v2 = extractLandmarksVector(two);
    // left hand (offset 63) should have non-zero entries
    expect(v2.slice(63).some((x) => x !== 0)).toBe(true);
  });
});

describe('analyzeFingerStates', () => {
  it('open palm (hello) has all four fingers extended', () => {
    const hands = getSimulatedHand('hello', 0);
    const fs = analyzeFingerStates(hands[0].landmarks);
    expect(fs.index).toBe(true);
    expect(fs.middle).toBe(true);
    expect(fs.ring).toBe(true);
    expect(fs.pinky).toBe(true);
  });

  it('peace sign: index+middle extended, ring+pinky folded', () => {
    const hands = getSimulatedHand('peace', 0);
    const fs = analyzeFingerStates(hands[0].landmarks);
    expect(fs.index).toBe(true);
    expect(fs.middle).toBe(true);
    expect(fs.ring).toBe(false);
    expect(fs.pinky).toBe(false);
  });

  it('I sign: only pinky extended', () => {
    const hands = getSimulatedHand('i', 0);
    const fs = analyzeFingerStates(hands[0].landmarks);
    expect(fs.pinky).toBe(true);
    expect(fs.index).toBe(false);
    expect(fs.middle).toBe(false);
    expect(fs.ring).toBe(false);
  });
});

describe('classifyHandGesture', () => {
  const cases: Array<[string, string]> = [
    ['hello', 'hello'],
    ['peace', 'peace'],
    ['love', 'love'],
    ['i', 'I'],
    ['eat', 'eat'],
    ['sleep', 'sleep'],
    ['not', 'not'],
    ['hate', 'hate'],
  ];
  for (const [input, expected] of cases) {
    it(`classifies "${input}" as "${expected}"`, () => {
      const hands = getSimulatedHand(input, 0);
      const res = classifyHandGesture(hands);
      expect(res).not.toBeNull();
      expect(res!.label).toBe(expected);
      expect(res!.confidence).toBeGreaterThan(0.9);
    });
  }

  it('classifies two-hand shawarma', () => {
    const hands = getSimulatedHand('shawarma', 0);
    const res = classifyHandGesture(hands);
    expect(res).not.toBeNull();
    expect(res!.label).toBe('Shawarma');
  });

  it('classifies two-hand tacos', () => {
    const hands = getSimulatedHand('tacos', 0);
    const res = classifyHandGesture(hands);
    expect(res).not.toBeNull();
    expect(res!.label).toBe('tacos');
  });

  it('returns null for empty hands', () => {
    expect(classifyHandGesture([])).toBeNull();
  });
});
