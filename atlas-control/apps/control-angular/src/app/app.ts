import { Component, inject, signal } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';
import { AuthService } from './core/auth';

@Component({
  imports: [RouterLink, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {
  auth = inject(AuthService);
  readonly year = signal(new Date().getFullYear());

  async signIn(): Promise<void> {
    await this.auth.signIn();
  }

  async signOut(): Promise<void> {
    await this.auth.signOut();
  }
}
