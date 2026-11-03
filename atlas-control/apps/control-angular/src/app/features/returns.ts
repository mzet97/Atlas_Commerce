import { Component, OnInit, inject, signal } from '@angular/core';
import { ControlApi } from '../core/control-api';

type Rma = {
  id: string;
  order_id: string;
  status: string;
  reason: string;
  refund_total_minor: number;
};

@Component({
  selector: 'app-returns',
  template: `
    <h1>Devoluções (RMA)</h1>
    <table data-testid="returns">
      <tr><th>id</th><th>pedido</th><th>status</th><th>motivo</th><th>refund</th><th></th></tr>
      @for (r of rmas(); track r.id) {
        <tr>
          <td>{{ r.id }}</td><td>{{ r.order_id }}</td><td>{{ r.status }}</td>
          <td>{{ r.reason }}</td><td>{{ r.refund_total_minor }}</td>
          <td>
            @if (r.status === 'REQUESTED') {
              <button (click)="approve(r.id)">aprovar</button>
            }
          </td>
        </tr>
      }
    </table>
    <p class="msg">{{ msg() }}</p>
  `,
})
export class ReturnsComponent implements OnInit {
  private api = inject(ControlApi);
  rmas = signal<Rma[]>([]);
  msg = signal('');

  async ngOnInit(): Promise<void> {
    await this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      this.rmas.set((await this.api.list<Rma[]>('/ops/fulfillment/returns')) ?? []);
    } catch (err) {
      this.msg.set(String(err));
    }
  }

  async approve(id: string): Promise<void> {
    try {
      await this.api.post(`/ops/fulfillment/returns/${id}/approve`, {
        correlation_id: crypto.randomUUID(),
      });
      await this.refresh();
    } catch (err) {
      this.msg.set(String(err));
    }
  }
}
