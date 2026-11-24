import { useState, useEffect } from 'react';
import {
  Bell,
  X,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Calendar,
  Sparkles,
  Volume2,
  Check,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext';
import {
  getNotificationPermission,
  requestNotificationPermission,
  sendNativeNotification,
} from '../../services/notificationService';
import { Button } from '../common/Button';

export function NotificationModal({ isOpen, onClose }) {
  const navigate = useNavigate();
  const {
    tasks,
    goals,
    toggleTaskCompletion,
    deadlineNotifications = [],
  } = useApp();

  const [activeTab, setActiveTab] = useState('ALL'); // 'ALL' | 'OVERDUE' | 'TODAY' | 'UPCOMING'
  const [permissionStatus, setPermissionStatus] = useState(getNotificationPermission());
  const [testSent, setTestSent] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setPermissionStatus(getNotificationPermission());
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleRequestPermission = async () => {
    const perm = await requestNotificationPermission();
    setPermissionStatus(perm);
    if (perm === 'granted') {
      await sendNativeNotification('🔔 NIYANTRAN Deadline Notifications Enabled', {
        body: 'You will now receive desktop alerts for overdue, due today, and high-priority deadlines!',
      });
    }
  };

  const handleSendTestNotification = async () => {
    setTestSent(true);
    await sendNativeNotification('⚡ NIYANTRAN Deadline Test Alert', {
      body: 'This is how your important deadline notifications will appear on your desktop!',
    });
    setTimeout(() => setTestSent(false), 3000);
  };

  // Filter items based on activeTab
  const overdueItems = deadlineNotifications.filter((n) => n.urgency === 'OVERDUE');
  const todayItems = deadlineNotifications.filter((n) => n.urgency === 'DUE_TODAY');
  const upcomingItems = deadlineNotifications.filter((n) => n.urgency === 'DUE_SOON');

  const filteredItems = deadlineNotifications.filter((n) => {
    if (activeTab === 'OVERDUE') return n.urgency === 'OVERDUE';
    if (activeTab === 'TODAY') return n.urgency === 'DUE_TODAY';
    if (activeTab === 'UPCOMING') return n.urgency === 'DUE_SOON';
    return true;
  });

  const handleItemClick = (item) => {
    onClose();
    if (item.type === 'task') {
      navigate('/tasks');
    } else {
      navigate('/goals');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/60 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="w-full max-w-xl glass-modal rounded-3xl shadow-2xl border border-white/70 dark:border-white/10 overflow-hidden flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-white/60 dark:border-white/10 flex items-center justify-between glass-silver-gradient">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-[#568B75]/20 dark:bg-[#75B798]/20 text-[#568B75] dark:text-[#75B798] flex items-center justify-center border border-[#568B75]/30 dark:border-[#75B798]/30 shadow-xs shrink-0">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                  Important Deadlines
                </h2>
                {deadlineNotifications.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-extrabold bg-[#568B75]/15 dark:bg-[#75B798]/20 text-[#568B75] dark:text-[#75B798] border border-[#568B75]/30 dark:border-[#75B798]/30">
                    {deadlineNotifications.length}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Real-time tracking of critical, due today, and upcoming milestones
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-white/40 dark:hover:bg-white/10 transition-colors"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Browser Permission Banner */}
        <div className="px-5 pt-4">
          {permissionStatus !== 'granted' ? (
            <div className="p-3.5 rounded-2xl bg-amber-500/10 dark:bg-amber-500/15 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-amber-900 dark:text-amber-200">
                    Browser notifications are not active
                  </p>
                  <p className="text-[11px] text-amber-700/80 dark:text-amber-300/80 mt-0.5">
                    Enable desktop alerts so you never miss an urgent deadline even when minimized.
                  </p>
                </div>
              </div>
              <Button
                size="sm"
                variant="primary"
                onClick={handleRequestPermission}
                className="shrink-0 text-xs shadow-xs"
              >
                Enable Notifications
              </Button>
            </div>
          ) : (
            <div className="px-3.5 py-2 rounded-xl bg-[#568B75]/10 dark:bg-[#75B798]/15 border border-[#568B75]/25 dark:border-[#75B798]/25 flex items-center justify-between text-xs">
              <div className="flex items-center gap-2 text-[#568B75] dark:text-[#75B798] font-medium">
                <ShieldCheck className="w-4 h-4" />
                <span>Desktop notifications are active</span>
              </div>
              <button
                type="button"
                onClick={handleSendTestNotification}
                disabled={testSent}
                className="text-[11px] font-semibold text-[#568B75] dark:text-[#75B798] hover:underline flex items-center gap-1 cursor-pointer disabled:opacity-50"
              >
                <Volume2 className="w-3.5 h-3.5" />
                <span>{testSent ? 'Sent!' : 'Send Test Alert'}</span>
              </button>
            </div>
          )}
        </div>

        {/* Filter Navigation Tabs */}
        <div className="px-5 pt-3 flex items-center gap-1.5 overflow-x-auto no-scrollbar border-b border-white/60 dark:border-white/10 pb-2.5">
          <button
            type="button"
            onClick={() => setActiveTab('ALL')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'ALL'
                ? 'bg-[#568B75] text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/5'
            }`}
          >
            All ({deadlineNotifications.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('OVERDUE')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'OVERDUE'
                ? 'bg-rose-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/5'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span>Overdue ({overdueItems.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('TODAY')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'TODAY'
                ? 'bg-amber-600 text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/5'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Due Today ({todayItems.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('UPCOMING')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
              activeTab === 'UPCOMING'
                ? 'bg-[#568B75] text-white shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:bg-white/40 dark:hover:bg-white/5'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-[#75B798]" />
            <span>Due Soon ({upcomingItems.length})</span>
          </button>
        </div>

        {/* Notifications List */}
        <div className="flex-1 overflow-y-auto p-5 space-y-3 no-scrollbar min-h-[220px]">
          {filteredItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <div className="w-12 h-12 rounded-2xl bg-[#568B75]/15 text-[#568B75] dark:text-[#75B798] flex items-center justify-center mb-3">
                <Sparkles className="w-6 h-6" />
              </div>
              <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                All caught up!
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-xs">
                No active deadline alerts in this category. You are on track with your goals and tasks.
              </p>
            </div>
          ) : (
            filteredItems.map((item) => {
              const isOverdue = item.urgency === 'OVERDUE';
              const isToday = item.urgency === 'DUE_TODAY';

              return (
                <div
                  key={item.id}
                  className={`p-3.5 rounded-2xl transition-all border flex items-start justify-between gap-3 group ${
                    isOverdue
                      ? 'bg-rose-50/70 dark:bg-rose-950/25 border-rose-200/80 dark:border-rose-900/40 hover:border-rose-300'
                      : isToday
                      ? 'bg-amber-50/70 dark:bg-amber-950/25 border-amber-200/80 dark:border-amber-900/40 hover:border-amber-300'
                      : 'glass-card hover:bg-white/80 dark:hover:bg-white/10'
                  }`}
                >
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => handleItemClick(item)}
                  >
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      {/* Urgency Badge */}
                      <span
                        className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-md border ${
                          isOverdue
                            ? 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/50 dark:text-rose-300 dark:border-rose-800'
                            : isToday
                            ? 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/50 dark:text-amber-300 dark:border-amber-800'
                            : 'bg-[#568B75]/15 text-[#568B75] border-[#568B75]/30 dark:bg-[#75B798]/20 dark:text-[#75B798] dark:border-[#75B798]/30'
                        }`}
                      >
                        {item.message}
                      </span>

                      {/* Priority Badge */}
                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                          item.priority === 'High'
                            ? 'bg-rose-500/10 text-rose-600 border-rose-500/20 dark:text-rose-400'
                            : 'bg-slate-500/10 text-slate-600 border-slate-500/20 dark:text-slate-400'
                        }`}
                      >
                        {item.priority} Priority
                      </span>

                      {/* Category Badge */}
                      <span className="text-[10px] text-slate-500 dark:text-slate-400 bg-white/50 dark:bg-white/5 px-1.5 py-0.5 rounded border border-white/60 dark:border-white/10">
                        {item.category}
                      </span>
                    </div>

                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white truncate group-hover:text-[#568B75] dark:group-hover:text-[#75B798] transition-colors">
                      {item.title}
                    </h4>

                    <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 mt-1">
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5" />
                        <span>Deadline: {item.dueDate}</span>
                      </span>
                      <span className="capitalize text-[11px] px-1.5 py-0.2 rounded bg-slate-200/50 dark:bg-slate-800">
                        {item.type}
                      </span>
                    </div>
                  </div>

                  {/* Quick Action Button */}
                  <div className="shrink-0 flex items-center gap-1 pt-1">
                    {item.type === 'task' && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleTaskCompletion(item.sourceId);
                        }}
                        className="p-1.5 rounded-xl bg-white/80 dark:bg-white/10 hover:bg-[#568B75] hover:text-white dark:hover:bg-[#75B798] dark:hover:text-[#101C18] text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-white/10 transition-colors shadow-2xs"
                        title="Mark Task as Completed"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleItemClick(item)}
                      className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-white/50 dark:hover:bg-white/10 transition-colors"
                      title="View Details"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/60 dark:border-white/10 bg-white/40 dark:bg-white/5 flex items-center justify-between">
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            {deadlineNotifications.length} active notification{deadlineNotifications.length !== 1 ? 's' : ''}
          </p>
          <Button size="sm" variant="outline" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </div>
  );
}
