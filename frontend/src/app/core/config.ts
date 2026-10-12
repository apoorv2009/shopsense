import { Injectable, signal } from '@angular/core';

export interface AppConfig {
  readonly apiBaseUrl: string;
  readonly mode: 'dev' | 'azure';
  readonly reviewerName: string;
}

/** Runtime configuration from public/config.json. No secrets belong here (CLAUDE.md §3). */
@Injectable({ providedIn: 'root' })
export class ConfigService {
  private readonly loaded = signal<AppConfig | null>(null);

  async load(): Promise<void> {
    const response = await fetch('/config.json', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`config.json could not be loaded (HTTP ${String(response.status)})`);
    }
    this.loaded.set((await response.json()) as AppConfig);
  }

  get current(): AppConfig {
    const config = this.loaded();
    if (config === null) {
      throw new Error('configuration used before it was loaded');
    }
    return config;
  }
}
