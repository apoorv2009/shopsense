import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { ShopSenseApi, StreamEvent, TicketView } from '../core/api';
import { PaisePipe } from '../shared/paise.pipe';

interface ChatLine {
  readonly from: 'customer' | 'assistant';
  readonly text: string;
}

interface CaseStatus {
  readonly label: string;
  readonly next: string;
}

const CASE_STATUS: Record<string, CaseStatus> = {
  greeting: { label: 'Welcome', next: 'Describe your problem to get started.' },
  answered: { label: 'Answered', next: 'No action needed.' },
  resolved: { label: 'Refund processed', next: 'No action needed.' },
  pending_human_approval: {
    label: 'Waiting for approval',
    next: 'A specialist reviews this refund and replies here.',
  },
  needs_customer_info: { label: 'Waiting for your details', next: 'Share the order number to continue.' },
  handed_off: { label: 'With a specialist', next: 'A specialist will get back to you shortly.' },
  parked_human_queue: { label: 'With a specialist', next: 'A specialist will follow up on this order.' },
  cannot_help: { label: 'Not possible', next: 'See the reply above for details.' },
  rejected: { label: 'Not approved', next: 'See the reply above for details.' },
  out_of_scope: { label: 'Out of scope', next: 'Ask about an order, delivery, return or refund.' },
};

const STEP_LABELS: Record<string, string> = {
  triage: 'Reading your message',
  lookup: 'Finding your order',
  advise: 'Checking the order details',
  assess: 'Checking the return policy',
  review: 'Passing it to a specialist',
  execute_auto: 'Processing your refund',
  approval: 'Waiting for a specialist to approve',
  execute_approved: 'Processing the approved refund',
  respond: 'Preparing your reply',
};

@Component({
  selector: 'ss-chat-page',
  imports: [
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    PaisePipe,
  ],
  templateUrl: './chat.page.html',
  styleUrl: './chat.page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatPage {
  private readonly api = inject(ShopSenseApi);

  readonly customerNo = signal('C0001');
  readonly draft = signal('');
  readonly busy = signal(false);
  readonly steps = signal<readonly string[]>([]);
  readonly lines = signal<readonly ChatLine[]>([]);
  readonly lastView = signal<TicketView | null>(null);
  readonly error = signal<string | null>(null);

  // The customer's earlier messages in this conversation, sent with each new message so the
  // assistant keeps context. Cleared when the customer number changes.
  private historyFor = '';
  private history: string[] = [];

  readonly stepLabel = (step: string): string => STEP_LABELS[step] ?? step;

  readonly caseStatus = computed<CaseStatus>(() => {
    const outcome = this.lastView()?.outcome;
    if (!outcome) {
      return { label: 'New', next: 'Describe your problem to get started.' };
    }
    return CASE_STATUS[outcome] ?? { label: outcome, next: '' };
  });

  async send(): Promise<void> {
    const text = this.draft().trim();
    if (text === '' || this.busy()) {
      return;
    }
    this.lines.update((lines) => [...lines, { from: 'customer', text }]);
    this.draft.set('');
    this.busy.set(true);
    this.error.set(null);
    this.steps.set([]);
    const customer = this.customerNo();
    if (customer !== this.historyFor) {
      this.history = [];
      this.historyFor = customer;
    }
    const earlier = this.history.slice(-4);
    try {
      await this.api.streamChat(customer, text, earlier, (event) => {
        this.onEvent(event);
      });
      this.history = [...this.history, text].slice(-5);
    } catch {
      this.error.set('We could not reach the support system. Please try again in a moment.');
    } finally {
      this.busy.set(false);
    }
  }

  private onEvent(event: StreamEvent): void {
    if (event.step !== undefined) {
      this.steps.update((steps) => [...steps, event.step ?? '']);
    }
    if (event.final !== undefined) {
      this.lastView.set(event.final);
      const reply = event.final.reply ?? 'Thanks, your message has been received.';
      this.lines.update((lines) => [...lines, { from: 'assistant', text: reply }]);
    }
  }
}
