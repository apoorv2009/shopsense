import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ConfigService } from '../core/config';
import { ShopSenseApi, TicketView } from '../core/api';
import { PaisePipe } from '../shared/paise.pipe';

@Component({
  selector: 'ss-console-page',
  imports: [
    FormsModule,
    PaisePipe,
  ],
  templateUrl: './console.page.html',
  styleUrl: './console.page.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConsolePage {
  private readonly api = inject(ShopSenseApi);
  private readonly config = inject(ConfigService);

  readonly ticketId = signal('');
  readonly view = signal<TicketView | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly decided = signal<string | null>(null);

  async load(): Promise<void> {
    const id = this.ticketId().trim();
    if (id === '') {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.decided.set(null);
    try {
      this.view.set(await this.api.getTicket(id));
    } catch {
      this.view.set(null);
      this.error.set('That ticket could not be found.');
    } finally {
      this.busy.set(false);
    }
  }

  async decide(approve: boolean): Promise<void> {
    const current = this.view();
    if (!current?.paused) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    try {
      const updated = await this.api.decide(
        current.ticket_id,
        approve,
        this.config.current.reviewerName,
      );
      this.view.set(updated);
      this.decided.set(
        approve ? 'Approved. The refund is being processed.' : 'Rejected. No refund was made.',
      );
    } catch {
      this.error.set('The decision could not be recorded. Please try again.');
    } finally {
      this.busy.set(false);
    }
  }
}
