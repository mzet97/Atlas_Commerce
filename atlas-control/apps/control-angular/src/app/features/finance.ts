import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ControlApi } from '../core/control-api';

type Approval = {
  approval_id: string;
  action: string;
  intent_id: string;
  resource_type: string;
  status: string;
  requested_by: string;
};

@Component({
  selector: 'app-finance',
  imports: [FormsModule],
  template: `
    <h1>Finance</h1>
    <h2>Aprovações pendentes (four-eyes)</h2>
    <table data-testid="approvals">
      <tr><th>id</th><th>ação</th><th>alvo</th><th>por</th><th></th></tr>
      @for (a of approvals(); track a.approval_id) {
        <tr>
          <td>{{ a.approval_id }}</td>
          <td>{{ a.action }}</td>
          <td>{{ a.intent_id }}</td>
          <td>{{ a.requested_by }}</td>
          <td>
            <button (click)="decide(a.approval_id, 'approve')">aprovar</button>
            <button (click)="decide(a.approval_id, 'reject')">rejeitar</button>
          </td>
        </tr>
      }
    </table>
    <h2>Pagamento</h2>
    <label>intent id <input [(ngModel)]="intentId" placeholder="pi-…" /></label>
    <button (click)="viewIntent()">ver</button>
    <button (click)="refund()">refund</button>
    <pre>{{ intentText() }}</pre>
    <p class="msg">{{ msg() }}</p>
  `,
})
export class FinanceComponent implements OnInit {
  private api = inject(ControlApi);
  approvals = signal<Approval[]>([]);
  intentId = '';
  intentText = signal('');
  msg = signal('');

  async ngOnInit(): Promise<void> {
    await this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      const rows = await this.api.list<Approval[]>('/ops/finance/approvals/pending');
      this.approvals.set(rows ?? []);
    } catch (err) {
      this.msg.set(String(err));
    }
  }

  async decide(id: string, action: 'approve' | 'reject'): Promise<void> {
    this.msg.set(
      await this.command(`/ops/finance/approvals/${id}/${action}`),
    );
    await this.refresh();
  }

  async viewIntent(): Promise<void> {
    try {
      const intent = await this.api.get(`/ops/finance/payments/${this.intentId}`);
      this.intentText.set(JSON.stringify(intent, null, 2));
    } catch (err) {
      this.msg.set(String(err));
    }
  }

  async refund(): Promise<void> {
    try {
      const result = await this.api.post(
        `/ops/finance/payments/${this.intentId}/refund`,
        { reason: 'admin ui', correlation_id: crypto.randomUUID() },
      );
      this.intentText.set(JSON.stringify(result, null, 2));
      this.msg.set('');
    } catch (err) {
      this.msg.set(String(err));
    }
  }

  private async command(path: string): Promise<string> {
    try {
      const result = await this.api.post(path, { correlation_id: crypto.randomUUID() });
      return JSON.stringify(result).slice(0, 200);
    } catch (err) {
      return String(err);
    }
  }
}
