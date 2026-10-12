import { Routes } from '@angular/router';

/** Feature areas load lazily (CLAUDE.md §2). Guards are UX only; the API enforces the rules. */
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'chat' },
  {
    path: 'chat',
    loadComponent: () => import('./customer/chat.page').then((m) => m.ChatPage),
  },
  {
    path: 'reviewer',
    loadComponent: () => import('./reviewer/console.page').then((m) => m.ConsolePage),
  },
  { path: '**', redirectTo: 'chat' },
];
