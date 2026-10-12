import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
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

  readonly stepLabel = (step: string): string => STEP_LABELS[step] ?? step;

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
    try {
      await this.api.streamChat(this.customerNo(), text, (event) => {
        this.onEvent(event);
      });
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
