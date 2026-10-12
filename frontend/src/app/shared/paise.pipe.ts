import { Pipe, PipeTransform } from '@angular/core';

const rupees = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 });

/**
 * The only place money is formatted for display (CLAUDE.md §2). Amounts arrive as integer paise
 * from the API; this pipe converts them to rupees for display and does no other arithmetic.
 */
@Pipe({ name: 'paise' })
export class PaisePipe implements PipeTransform {
  transform(paise: number | null | undefined): string {
    if (paise === null || paise === undefined) {
      return 'not stated';
    }
    return `₹${rupees.format(paise / 100)}`;
  }
}
