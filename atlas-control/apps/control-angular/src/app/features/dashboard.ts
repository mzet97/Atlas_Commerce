import { Component, OnInit, inject, signal } from '@angular/core';
import { AuthService } from '../core/auth';
import { ControlApi } from '../core/control-api';

@Component({
  selector: 'app-dashboard',
  template: `
    <h1>Atlas Control</h1>
    <p data-testid="user">operador: {{ username() }}</p>
    <p>Escolha um módulo na barra lateral. Toda ação é auditada no control-api
    (ABAC por escopo, four-eyes acima do threshold).</p>
  `,
})
export class DashboardComponent implements OnInit {
  auth = inject(AuthService);
  api = inject(ControlApi);
  username = signal('(anon)');

  async ngOnInit(): Promise<void> {
    this.username.set((await this.auth.username()) || '(anon)');
  }
}
