import { useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight, Clock } from 'lucide-react';
import { Card, CardHeader } from '../components/common/Card';

export function Calendar() {
  const [selectedDay, setSelectedDay] = useState(17);

  const daysInNov = 30;

  const scheduleEvents = {
    14: [{ title: 'OS Lab Submission (Overdue)', type: 'deadline', color: 'rose' }],
    17: [
      { title: 'CS229 SVM Derivations', type: 'academic', color: 'blue' },
      { title: 'LeetCode 3 Graph Problems', type: 'coding', color: 'indigo' },
      { title: 'DDIA Ch 5 Reading', type: 'reading', color: 'cyan' },
    ],
    18: [{ title: 'NIYANTRA Phase 1 Review', type: 'project', color: 'indigo' }],
    20: [{ title: 'CS229 Problem Set 3', type: 'deadline', color: 'amber' }],
    22: [{ title: 'RoBERTa Classifier Eval', type: 'coding', color: 'violet' }],
    25: [{ title: 'NIYANTRA Phase 1 Handover', type: 'deadline', color: 'indigo' }],
  };

  const selectedEvents = scheduleEvents[selectedDay] || [];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Main Month Grid */}
        <div className="flex-1">
          <Card>
            <div className="flex items-center justify-between pb-4 border-b border-white/60 dark:border-white/10">
              <div className="flex items-center gap-2">
                <CalendarDays className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                <h3 className="font-bold text-lg text-slate-900 dark:text-white">
                  November 2026
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <button className="p-1.5 rounded-lg border border-white/60 dark:border-white/10 bg-white/30 dark:bg-white/5 hover:bg-white/50 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300">
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button className="px-3 py-1 rounded-lg border border-white/60 dark:border-white/10 bg-white/30 dark:bg-white/5 text-xs font-semibold hover:bg-white/50 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300">
                  Today
                </button>
                <button className="p-1.5 rounded-lg border border-white/60 dark:border-white/10 bg-white/30 dark:bg-white/5 hover:bg-white/50 dark:hover:bg-white/10 text-slate-700 dark:text-slate-300">
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Days of week */}
            <div className="grid grid-cols-7 gap-2 mt-4 text-center text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider pb-2 border-b border-slate-100 dark:border-slate-800/60">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
                <div key={d}>{d}</div>
              ))}
            </div>

            {/* Calendar Days */}
            <div className="grid grid-cols-7 gap-2 mt-2">
              {Array.from({ length: daysInNov }).map((_, i) => {
                const day = i + 1;
                const isSelected = selectedDay === day;
                const isToday = day === 17;
                const events = scheduleEvents[day] || [];

                return (
                  <button
                    key={day}
                    type="button"
                    onClick={() => setSelectedDay(day)}
                    className={`min-h-[72px] sm:min-h-[88px] p-1.5 rounded-xl border text-left flex flex-col justify-between transition-all cursor-pointer ${
                      isSelected
                        ? 'border-primary-500 ring-2 ring-primary-500/20 bg-primary-50/40 dark:bg-primary-950/30'
                        : isToday
                        ? 'border-primary-400 dark:border-primary-700 bg-primary-50/20 dark:bg-primary-900/20'
                        : 'border-white/50 dark:border-white/10 hover:border-primary-300 dark:hover:border-primary-600 bg-white/40 dark:bg-white/5'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`text-xs font-bold w-6 h-6 rounded-lg flex items-center justify-center ${
                          isToday
                            ? 'bg-primary-600 dark:bg-primary-500 text-white shadow-xs'
                            : isSelected
                            ? 'text-primary-600 dark:text-primary-400'
                            : 'text-slate-700 dark:text-slate-300'
                        }`}
                      >
                        {day}
                      </span>
                    </div>

                    <div className="space-y-1 mt-1">
                      {events.map((ev, evIdx) => (
                        <div
                          key={evIdx}
                          className="text-[9px] font-semibold px-1.5 py-0.5 rounded truncate bg-primary-100/70 dark:bg-primary-950/60 text-primary-800 dark:text-primary-200 border border-primary-200/50 dark:border-primary-800/50"
                        >
                          {ev.title}
                        </div>
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Selected Day Agenda */}
        <div className="lg:w-80">
          <Card>
            <CardHeader
              title={`Agenda: Nov ${selectedDay}, 2026`}
              subtitle={selectedDay === 17 ? 'Today' : 'Scheduled activities'}
              icon={Clock}
            />

            <div className="space-y-3 mt-4">
              {selectedEvents.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <p className="text-xs">No scheduled milestones for this day.</p>
                </div>
              ) : (
                selectedEvents.map((ev, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-xl border border-white/60 dark:border-white/10 bg-white/40 dark:bg-white/5 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-900 dark:text-white">
                        {ev.title}
                      </span>
                      <span className="text-[10px] uppercase font-semibold text-primary-600 dark:text-primary-400">
                        {ev.type}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500">Scheduled deliverable checkpoint</p>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
