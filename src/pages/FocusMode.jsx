import { useState, useEffect } from 'react';
import { Play, Pause, RotateCcw, Target } from 'lucide-react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useApp } from '../context/AppContext';

export function FocusMode() {
  const { tasks } = useApp();
  const [mode, setMode] = useState('focus'); // focus (25), shortBreak (5), longBreak (15)
  const [timeLeft, setTimeLeft] = useState(25 * 60);
  const [isRunning, setIsRunning] = useState(false);
  const [selectedTask, setSelectedTask] = useState(tasks[0]?.title || 'Solve 3 Hard Graph Problems');

  const handleModeChange = (newMode) => {
    setMode(newMode);
    setIsRunning(false);
    if (newMode === 'focus') setTimeLeft(25 * 60);
    if (newMode === 'shortBreak') setTimeLeft(5 * 60);
    if (newMode === 'longBreak') setTimeLeft(15 * 60);
  };

  useEffect(() => {
    let timer = null;
    if (isRunning && timeLeft > 0) {
      timer = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            setIsRunning(false);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isRunning, timeLeft]);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;
  const formattedTime = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

  const resetTimer = () => {
    setIsRunning(false);
    if (mode === 'focus') setTimeLeft(25 * 60);
    if (mode === 'shortBreak') setTimeLeft(5 * 60);
    if (mode === 'longBreak') setTimeLeft(15 * 60);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 text-center animate-in fade-in duration-200">
      {/* Mode Switcher */}
      <div className="inline-flex p-1.5 rounded-2xl bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-800 shadow-card">
        <button
          type="button"
          onClick={() => handleModeChange('focus')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            mode === 'focus'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          Pomodoro Focus (25m)
        </button>
        <button
          type="button"
          onClick={() => handleModeChange('shortBreak')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            mode === 'shortBreak'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          Short Break (5m)
        </button>
        <button
          type="button"
          onClick={() => handleModeChange('longBreak')}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            mode === 'longBreak'
              ? 'bg-indigo-600 text-white shadow-xs'
              : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
          }`}
        >
          Long Break (15m)
        </button>
      </div>

      {/* Main Focus Chamber Card */}
      <Card className="p-8 sm:p-12 border border-slate-200/90 dark:border-slate-800">
        {/* Selected Task Anchor & Selector */}
        <div className="mb-6 flex flex-col sm:flex-row items-center justify-center gap-2 text-xs font-semibold max-w-md mx-auto">
          <div className="flex items-center gap-2 text-indigo-600 dark:text-indigo-400 bg-indigo-50/60 dark:bg-indigo-950/40 py-2 px-3 rounded-xl border border-indigo-200/60 dark:border-indigo-800/60 w-full sm:w-auto truncate">
            <Target className="w-4 h-4 shrink-0" />
            <select
              value={selectedTask}
              onChange={(e) => setSelectedTask(e.target.value)}
              className="bg-transparent border-none text-xs font-semibold focus:outline-none cursor-pointer truncate max-w-xs"
            >
              {tasks.map((t) => (
                <option key={t.id} value={t.title} className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
                  {t.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Large Digital Display */}
        <div className="my-8">
          <span className="font-mono text-7xl sm:text-8xl font-black text-slate-900 dark:text-white tracking-tighter select-none">
            {formattedTime}
          </span>
          <p className="text-xs uppercase tracking-widest text-slate-400 font-bold mt-2">
            {isRunning ? 'Flow State Active' : 'Session Paused'}
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-center gap-4 mt-8">
          <Button
            variant="primary"
            size="lg"
            icon={isRunning ? Pause : Play}
            onClick={() => setIsRunning(!isRunning)}
            className="w-36 text-base font-bold shadow-lg shadow-indigo-500/25"
          >
            {isRunning ? 'Pause' : 'Start Focus'}
          </Button>

          <Button
            variant="secondary"
            size="lg"
            icon={RotateCcw}
            onClick={resetTimer}
            title="Reset timer"
          >
            Reset
          </Button>
        </div>
      </Card>
    </div>
  );
}
