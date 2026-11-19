import { DashboardHeader } from '../components/dashboard/DashboardHeader';
import { OverviewCards } from '../components/dashboard/OverviewCards';
import { TodayOverview } from '../components/dashboard/TodayOverview';
import { ProductivitySection } from '../components/dashboard/ProductivitySection';

export function Dashboard() {
  return (
    <div className="space-y-6 sm:space-y-8 animate-in fade-in duration-200">
      {/* Header with greeting, date, and quick action */}
      <DashboardHeader />

      {/* Top 4 Overview Metric Cards */}
      <OverviewCards />

      {/* Today's Execution Agenda and Priorities */}
      <TodayOverview />

      {/* Productivity & Analytics Charts */}
      <ProductivitySection />
    </div>
  );
}
