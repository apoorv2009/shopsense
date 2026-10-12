import { Injectable, computed, inject } from '@angular/core';

import { ConfigService } from './config';

export type Role = 'customer' | 'reviewer';

/**
 * Role for the current session. In `dev` mode the role is chosen by the page that is opened.
 * MSAL sign-in (auth code + PKCE, CLAUDE.md §3) replaces this once the Entra app registration
 * exists; route guards built on this are UX only, and the API enforces the real rules.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly config = inject(ConfigService);
  readonly isDev = computed(() => this.config.current.mode === 'dev');
}
