import { Routes } from '@angular/router';
import { CallbackComponent } from './features/callback';
import { DashboardComponent } from './features/dashboard';
import { FinanceComponent } from './features/finance';
import { CouponsComponent } from './features/coupons';
import { OrdersComponent } from './features/orders';
import { ReturnsComponent } from './features/returns';

// App is the bootstrapped shell; features mount into its router-outlet.
export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'orders', component: OrdersComponent },
  { path: 'finance', component: FinanceComponent },
  { path: 'coupons', component: CouponsComponent },
  { path: 'returns', component: ReturnsComponent },
  { path: 'callback', component: CallbackComponent },
];
