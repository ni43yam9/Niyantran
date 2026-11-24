import { Outlet, useLocation } from 'react-router-dom';
import { PanelRight } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { MobileHeader } from './MobileHeader';
import { MobileBottomNav } from './MobileBottomNav';
import { RightPanel } from './RightPanel';
import { TaskModal } from '../tasks/TaskModal';
import { GoalModal } from '../goals/GoalModal';
import { NotificationModal } from './NotificationModal';
import { useApp } from '../../context/AppContext';

export function Layout() {
  const location = useLocation();
  const {
    isRightPanelOpen,
    setIsRightPanelOpen,
    isTaskModalOpen,
    closeAddTaskModal,
    editingTask,
    isGoalModalOpen,
    closeAddGoalModal,
    editingGoal,
    isNotificationOpen,
    closeNotificationCenter,
  } = useApp();

  // Show right panel primarily on Dashboard or Tasks unless user collapsed it
  const showRightPanel = isRightPanelOpen && (location.pathname === '/' || location.pathname === '/tasks');

  return (
    <div className="min-h-screen bg-transparent text-slate-900 dark:text-slate-100 flex flex-col antialiased transition-colors duration-300">
      {/* Mobile Top Header */}
      <MobileHeader />

      <div className="flex flex-1 w-full min-h-0">
        {/* Desktop Sidebar */}
        <Sidebar />

        {/* Center Main Work Area */}
        <div className="flex-1 flex flex-col min-w-0 pb-20 md:pb-6 relative">
          {/* Floating Right Panel Trigger for Desktop when collapsed */}
          {!showRightPanel && (location.pathname === '/' || location.pathname === '/tasks') && (
            <button
              type="button"
              onClick={() => setIsRightPanelOpen(true)}
              className="hidden xl:flex fixed top-4 right-4 z-20 items-center gap-1.5 px-3 py-1.5 rounded-xl glass-card text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-sage-primary dark:hover:text-forest-primary transition-all cursor-pointer"
              title="Open Agenda & Priorities Panel"
            >
              <PanelRight className="w-4 h-4 text-sage-primary dark:text-forest-primary" />
              <span>Agenda</span>
            </button>
          )}

          {/* Page Outlet */}
          <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
            <Outlet />
          </main>
        </div>

        {/* Desktop Right Agenda Panel */}
        {showRightPanel && (
          <RightPanel onClose={() => setIsRightPanelOpen(false)} />
        )}
      </div>

      {/* Mobile Bottom Navigation */}
      <MobileBottomNav />

      {/* Reusable Modals */}
      <TaskModal
        isOpen={isTaskModalOpen}
        onClose={closeAddTaskModal}
        editingTask={editingTask}
      />

      <GoalModal
        isOpen={isGoalModalOpen}
        onClose={closeAddGoalModal}
        editingGoal={editingGoal}
      />

      {/* Deadline Notifications Center Modal */}
      <NotificationModal
        isOpen={isNotificationOpen}
        onClose={closeNotificationCenter}
      />
    </div>
  );
}
