import { describe, expect, it } from 'vitest';

import { PaisePipe } from './paise.pipe';

describe('PaisePipe', () => {
  const pipe = new PaisePipe();

  it('shows whole rupees from integer paise', () => {
    expect(pipe.transform(149900)).toBe('₹1,499');
  });

  it('keeps paise when they are present', () => {
    expect(pipe.transform(12345)).toBe('₹123.45');
  });

  it('says so when no amount is stated', () => {
    expect(pipe.transform(null)).toBe('not stated');
    expect(pipe.transform(undefined)).toBe('not stated');
  });
});
