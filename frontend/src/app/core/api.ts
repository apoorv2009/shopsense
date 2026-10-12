import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ConfigService } from './config';

/** A reviewer brief is written by an AI agent, so the console labels it as advisory. */
export interface ReviewBrief {
  readonly summary: string;
  readonly risk_notes: readonly string[];
  readonly recommendation: string;
}

export interface Approval {
  readonly ticket_id: string;
  readonly order_no: string | null;
  readonly sku: string | null;
  readonly amount_paise: number | null;
  readonly reasons: readonly string[];
  readonly brief?: ReviewBrief | null;
}

/** Mirrors the API's TicketView (adapters/workflow/runner.py). */
export interface TicketView {
  readonly ticket_id: string;
  readonly outcome: string | null;
  readonly paused: boolean;
  readonly route: string | null;
  readonly reply: string | null;
  readonly approval: Approval | null;
  readonly eligibility: string | null;
  readonly rule_id: string | null;
  readonly amount_paise: number | null;
  readonly issue_type: string | null;
}

export interface StreamEvent {
  readonly step?: string;
  readonly paused?: boolean;
  readonly outcome?: string | null;
  readonly final?: TicketView;
}

/**
 * Splits buffered server-sent events into complete events. An incomplete trailing block is kept
 * in `rest` until the next chunk arrives.
 */
export function parseSseEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const blocks = buffer.split('\n\n');
  const rest = blocks.pop() ?? '';
  const events: StreamEvent[] = [];
  for (const block of blocks) {
    const data = block.split('\n').find((line) => line.startsWith('data: '));
    if (data !== undefined) {
      events.push(JSON.parse(data.slice('data: '.length)) as StreamEvent);
    }
  }
  return { events, rest };
}

/** The only place components reach the API. Components never call HttpClient directly. */
@Injectable({ providedIn: 'root' })
export class ShopSenseApi {
  private readonly http = inject(HttpClient);
  private readonly config = inject(ConfigService);

  startChat(customerNo: string, message: string): Promise<TicketView> {
    return firstValueFrom(
      this.http.post<TicketView>(`${this.config.current.apiBaseUrl}/v1/chat/tickets`, {
        customer_no: customerNo,
        message,
      }),
    );
  }

  getTicket(ticketId: string): Promise<TicketView> {
    return firstValueFrom(
      this.http.get<TicketView>(`${this.config.current.apiBaseUrl}/v1/tickets/${ticketId}`),
    );
  }

  decide(ticketId: string, approve: boolean, reviewer: string): Promise<TicketView> {
    return firstValueFrom(
      this.http.post<TicketView>(
        `${this.config.current.apiBaseUrl}/v1/tickets/${ticketId}/decision`,
        { approve, reviewer },
      ),
    );
  }

  /** Streams one event per workflow step over server-sent events, then the final view. */
  async streamChat(
    customerNo: string,
    message: string,
    onEvent: (event: StreamEvent) => void,
  ): Promise<void> {
    const response = await fetch(`${this.config.current.apiBaseUrl}/v1/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_no: customerNo, message }),
    });
    if (!response.ok || response.body === null) {
      throw new Error(`chat stream failed (HTTP ${String(response.status)})`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSseEvents(buffer);
      buffer = parsed.rest;
      parsed.events.forEach(onEvent);
    }
  }
}
