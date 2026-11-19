import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AppProvider } from './context/AppContext';
import { Layout } from './components/layout/Layout';
import { ErrorBoundary } from './components/common/ErrorBoundary';

// Code-split route components
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const MyTasks = lazy(() => import('./pages/MyTasks').then((m) => ({ default: m.MyTasks })));
const Goals = lazy(() => import('./pages/Goals').then((m) => ({ default: m.Goals })));
const DailyPlanner = lazy(() => import('./pages/DailyPlanner').then((m) => ({ default: m.DailyPlanner })));
const Calendar = lazy(() => import('./pages/Calendar').then((m) => ({ default: m.Calendar })));
const Habits = lazy(() => import('./pages/Habits').then((m) => ({ default: m.Habits })));
const FocusMode = lazy(() => import('./pages/FocusMode').then((m) => ({ default: m.FocusMode })));
const Analytics = lazy(() => import('./pages/Analytics').then((m) => ({ default: m.Analytics })));
const Recommendations = lazy(() => import('./pages/Recommendations').then((m) => ({ default: m.Recommendations })));

function PageLoadingFallback() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-2.5">
        <div className="w-7 h-7 rounded-full border-2 border-indigo-600 border-t-transparent animate-spin" />
        <span className="text-xs font-semibold text-slate-400">Loading...</span>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AppProvider>
          <BrowserRouter>
            <Suspense fallback={<PageLoadingFallback />}>
              <Routes>
                <Route path="/" element={<Layout />}>
                  <Route index element={<Dashboard />} />
                  <Route path="tasks" element={<MyTasks />} />
                  <Route path="goals" element={<Goals />} />
                  <Route path="planner" element={<DailyPlanner />} />
                  <Route path="calendar" element={<Calendar />} />
                  <Route path="habits" element={<Habits />} />
                  <Route path="focus" element={<FocusMode />} />
                  <Route path="analytics" element={<Analytics />} />
                  <Route path="recommendations" element={<Recommendations />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </AppProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
