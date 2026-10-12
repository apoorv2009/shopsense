import { describe, expect, it } from 'vitest';

import { parseSseEvents } from './api';

describe('parseSseEvents', () => {
  it('reads complete events and keeps an incomplete tail', () => {
    const buffer = 'data: {"step":"triage"}\n\ndata: {"step":"lo';
    const { events, rest } = parseSseEvents(buffer);
    expect(events).toEqual([{ step: 'triage' }]);
    expect(rest).toBe('data: {"step":"lo');
  });

  it('completes an event once the rest arrives', () => {
    const first = parseSseEvents('data: {"step":"lookup"}\n\ndata: {"final":');
    const second = parseSseEvents(first.rest + '{"outcome":"resolved"}}\n\n');
    expect(first.events).toEqual([{ step: 'lookup' }]);
    expect(second.events).toEqual([{ final: { outcome: 'resolved' } }]);
    expect(second.rest).toBe('');
  });

  it('ignores blocks without a data line', () => {
    expect(parseSseEvents(': keep-alive\n\n').events).toEqual([]);
  });
});
