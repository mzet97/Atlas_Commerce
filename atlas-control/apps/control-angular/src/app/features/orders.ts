import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlApi } from '../core/control-api';

@Component({
  selector: 'app-orders',
  template: `
    <h1>Order Ops</h1>
    <label>order id <input [(ngModel)]="orderId" placeholder="o-…" /></label>
    <button (click)="view()">ver</button>
    <button (click)="ship()" [disabled]="!order()">ship</button>
    <button (click)="cancel()" [disabled]="!order()">cancel</button>
    <pre data-testid="order-view">{{ viewText() }}</pre>
    <p class="msg">{{ msg() }}</p>
  `,
  imports: [FormsModule],
})
export class OrdersComponent {
  private api = inject(ControlApi);
  orderId = '';
  order = signal<unknown>(null);
  viewText = signal('');
  msg = signal('');

  async view(): Promise<void> {
    try {
      const order = await this.api.get(`/ops/fulfillment/orders/${this.orderId}`);
      this.order.set(order);
      this.viewText.set(JSON.stringify(order, null, 2));
      this.msg.set('');
    } catch (err) {
      this.msg.set(String(err));
    }
  }

  async ship(): Promise<void> {
    this.msg.set(await this.command(`/ops/fulfillment/orders/${this.orderId}/ship`));
  }

  async cancel(): Promise<void> {
    this.msg.set(await this.command(`/ops/orders/${this.orderId}/cancel`));
  }

  private async command(path: string): Promise<string> {
    try {
      const result = await this.api.post(path, { correlation_id: crypto.randomUUID() });
      await this.view();
      return JSON.stringify(result).slice(0, 200);
    } catch (err) {
      return String(err);
    }
  }
}
