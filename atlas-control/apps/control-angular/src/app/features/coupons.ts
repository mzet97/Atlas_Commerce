import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlApi } from '../core/control-api';

type Coupon = {
  code: string;
  kind: string;
  value: number;
  market_id: string | null;
  active: boolean;
};

@Component({
  selector: 'app-coupons',
  imports: [FormsModule],
  template: `
    <h1>Cupons</h1>
    <table data-testid="coupons">
      <tr><th>código</th><th>tipo</th><th>valor</th><th>mercado</th><th>ativo</th><th></th></tr>
      @for (c of coupons(); track c.code) {
        <tr>
          <td>{{ c.code }}</td><td>{{ c.kind }}</td><td>{{ c.value }}</td>
          <td>{{ c.market_id || '—' }}</td><td>{{ c.active }}</td>
          <td><button [disabled]="!c.active" (click)="deactivate(c.code)">desativar</button></td>
        </tr>
      }
    </table>
    <h2>Novo</h2>
    <label>código <input [(ngModel)]="code" /></label>
    <select [(ngModel)]="kind"><option>PERCENT</option><option>FIXED</option></select>
    <label>valor <input type="number" [(ngModel)]="value" /></label>
    <label>mercado <input [(ngModel)]="market" placeholder="BR (opcional)" /></label>
    <button (click)="create()">criar</button>
    <p class="msg">{{ msg() }}</p>
  `,
})
export class CouponsComponent implements OnInit {
  private api = inject(ControlApi);
  coupons = signal<Coupon[]>([]);
  code = '';
  kind = 'PERCENT';
  value = 10;
  market = '';
  msg = signal('');

  async ngOnInit(): Promise<void> {
    await this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      this.coupons.set((await this.api.list<Coupon[]>('/ops/coupons')) ?? []);
    } catch (err) {
      this.msg.set(String(err));
    }
  }

  async create(): Promise<void> {
    this.msg.set(
      await this.command('/ops/coupons', {
        code: this.code,
        kind: this.kind,
        value: Number(this.value),
        market_id: this.market || null,
        correlation_id: crypto.randomUUID(),
      }),
    );
    await this.refresh();
  }

  async deactivate(code: string): Promise<void> {
    this.msg.set(
      await this.command(`/ops/coupons/${code}/deactivate`, {
        correlation_id: crypto.randomUUID(),
      }),
    );
    await this.refresh();
  }

  private async command(path: string, body: unknown): Promise<string> {
    try {
      await this.api.post(path, body);
      return 'ok';
    } catch (err) {
      return String(err);
    }
  }
}
