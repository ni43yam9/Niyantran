import { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  GitMerge,
  History,
  Laptop,
  Smartphone,
  X,
  RefreshCw,
  Edit3,
} from 'lucide-react';
import { db } from '../../database/db';
import {
  conflictDetector,
  conflictResolver,
  entityMergeHelpers,
  RESOLUTION_STRATEGY,
  registerConflictListener,
} from '../../sync';
import { syncManager } from '../../sync/syncManager';

export function ConflictResolutionModal({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('unresolved'); // 'unresolved' | 'history'
  const [unresolvedConflicts, setUnresolvedConflicts] = useState([]);
  const [conflictHistory, setConflictHistory] = useState([]);
  const [selectedConflict, setSelectedConflict] = useState(null);
  const [isMerging, setIsMerging] = useState(false);
  const [mergeOverrides, setMergeOverrides] = useState({});
  const [isResolving, setIsResolving] = useState(false);
  const [actionMessage, setActionMessage] = useState(null);

  const loadConflicts = useCallback(async () => {
    try {
      const activeUserId = db.getActiveUserId();
      const unresolved = await conflictDetector.getUnresolvedConflicts(activeUserId, db);
      const history = await conflictDetector.getConflictHistory(activeUserId, db);
      setUnresolvedConflicts(unresolved);
      setConflictHistory(history);

      if (unresolved.length > 0) {
        if (!selectedConflict || !unresolved.find((c) => c.id === selectedConflict.id)) {
          setSelectedConflict(unresolved[0]);
          setIsMerging(false);
          setMergeOverrides({});
        }
      } else {
        setSelectedConflict(null);
        setIsMerging(false);
      }
    } catch (err) {
      console.warn('Failed to load conflicts:', err);
    }
  }, [selectedConflict]);

  useEffect(() => {
    if (isOpen) {
      loadConflicts();
    }
  }, [isOpen, loadConflicts]);

  useEffect(() => {
    const unsub = registerConflictListener(() => {
      loadConflicts();
    });
    return () => unsub();
  }, [loadConflicts]);

  if (!isOpen) return null;

  const handleKeepLocal = async (conflict) => {
    if (!conflict) return;
    setIsResolving(true);
    setActionMessage('Preserving local version and broadcasting update...');
    try {
      await conflictResolver.resolveConflict({
        conflictId: conflict.id,
        strategy: RESOLUTION_STRATEGY.KEEP_LOCAL,
        targetDb: db,
      });
      // Trigger background sync to propagate winning version
      void syncManager.pushChanges({ targetDb: db });
      await loadConflicts();
      setActionMessage('Local version preserved and queued for synchronization.');
      setTimeout(() => setActionMessage(null), 3000);
    } catch (e) {
      console.error('Error resolving conflict with Keep Local:', e);
      setActionMessage(`Error: ${e.message}`);
    } finally {
      setIsResolving(false);
    }
  };

  const handleKeepRemote = async (conflict) => {
    if (!conflict) return;
    setIsResolving(true);
    setActionMessage('Adopting remote version...');
    try {
      await conflictResolver.resolveConflict({
        conflictId: conflict.id,
        strategy: RESOLUTION_STRATEGY.KEEP_REMOTE,
        targetDb: db,
      });
      await loadConflicts();
      setActionMessage('Remote version adopted and local edits superseded.');
      setTimeout(() => setActionMessage(null), 3000);
    } catch (e) {
      console.error('Error resolving conflict with Keep Remote:', e);
      setActionMessage(`Error: ${e.message}`);
    } finally {
      setIsResolving(false);
    }
  };

  const handleStartMerge = (conflict) => {
    setIsMerging(true);
    const initial = {};
    const local = conflict.localData || {};
    const remote = conflict.remoteData || {};

    // Default merge selections: prefer local for title/notes, remote for date if newer
    Object.keys(local).forEach((key) => {
      if (key !== 'version' && key !== 'updatedAt' && key !== 'createdAt') {
        initial[key] = local[key] !== undefined ? local[key] : remote[key];
      }
    });
    setMergeOverrides(initial);
  };

  const handleSaveMerge = async (conflict) => {
    if (!conflict) return;
    setIsResolving(true);
    setActionMessage('Applying merged fields and synchronizing...');
    try {
      let finalMergedData = { ...conflict.localData, ...mergeOverrides };
      if (conflict.entityType === 'task') {
        finalMergedData = entityMergeHelpers.mergeTasks(conflict.localData, conflict.remoteData, mergeOverrides);
      } else if (conflict.entityType === 'goal') {
        finalMergedData = entityMergeHelpers.mergeGoals(conflict.localData, conflict.remoteData, mergeOverrides);
      } else if (conflict.entityType === 'habit') {
        finalMergedData = entityMergeHelpers.mergeHabits(conflict.localData, conflict.remoteData, mergeOverrides);
      }

      await conflictResolver.resolveConflict({
        conflictId: conflict.id,
        strategy: RESOLUTION_STRATEGY.MANUAL_MERGE,
        mergedData: finalMergedData,
        targetDb: db,
      });

      // Broadcast merged result
      void syncManager.pushChanges({ targetDb: db });
      setIsMerging(false);
      await loadConflicts();
      setActionMessage('Merge applied and uploaded successfully.');
      setTimeout(() => setActionMessage(null), 3000);
    } catch (e) {
      console.error('Error saving merged conflict:', e);
      setActionMessage(`Error: ${e.message}`);
    } finally {
      setIsResolving(false);
    }
  };

  // Inspect fields for side-by-side comparison
  const getRelevantFields = (conflict) => {
    if (!conflict) return [];
    const local = conflict.localData || {};
    const remote = conflict.remoteData || {};
    const allKeys = Array.from(new Set([...Object.keys(local), ...Object.keys(remote)]));
    const excludedKeys = new Set(['id', 'userId', 'deviceUuid', 'version', 'createdAt', 'updatedAt', 'isDeleted', 'deletedAt']);

    return allKeys
      .filter((k) => !excludedKeys.has(k))
      .map((key) => {
        const localVal = local[key];
        const remoteVal = remote[key];
        const isDifferent = JSON.stringify(localVal) !== JSON.stringify(remoteVal);
        return { key, localVal, remoteVal, isDifferent };
      });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity animate-in fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog Card */}
      <div
        className="relative w-full max-w-4xl bg-white dark:bg-[#131B2E] border border-slate-200 dark:border-slate-800 rounded-2xl shadow-modal overflow-hidden z-10 transition-all transform duration-200 ease-out my-6 flex flex-col max-h-[90vh]"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-900/40 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                Synchronization Conflicts
                {unresolvedConflicts.length > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950/80 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
                    {unresolvedConflicts.length} Unresolved
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Review and resolve divergent changes made across offline devices.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-4 px-6 border-b border-slate-200 dark:border-slate-800 shrink-0 bg-white dark:bg-[#131B2E]">
          <button
            onClick={() => setActiveTab('unresolved')}
            className={`py-3 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
              activeTab === 'unresolved'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <GitMerge className="w-4 h-4" />
            Unresolved ({unresolvedConflicts.length})
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`py-3 text-xs font-semibold flex items-center gap-1.5 border-b-2 transition-colors ${
              activeTab === 'history'
                ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <History className="w-4 h-4" />
            Resolution History ({conflictHistory.length})
          </button>
        </div>

        {/* Action Status Banner */}
        {actionMessage && (
          <div className="px-6 py-2 bg-indigo-50 dark:bg-indigo-950/60 border-b border-indigo-200 dark:border-indigo-800/60 text-xs text-indigo-700 dark:text-indigo-300 flex items-center justify-between shrink-0">
            <span>{actionMessage}</span>
            {isResolving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
          </div>
        )}

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'unresolved' ? (
            unresolvedConflicts.length === 0 ? (
              <div className="py-16 text-center">
                <div className="w-12 h-12 rounded-full bg-emerald-100 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mx-auto mb-3">
                  <CheckCircle className="w-6 h-6" />
                </div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                  No Conflicts Detected
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
                  All local modifications and remote sync streams are completely reconciled across your devices.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Conflict List Selector */}
                <div className="lg:col-span-4 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-100 dark:divide-slate-800/60">
                  <div className="px-3.5 py-2.5 bg-slate-50 dark:bg-slate-900/40 text-xs font-semibold text-slate-600 dark:text-slate-400">
                    Select Item to Resolve
                  </div>
                  <div className="max-h-[380px] overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/60">
                    {unresolvedConflicts.map((c) => {
                      const isSelected = selectedConflict?.id === c.id;
                      const title = c.localData?.title || c.remoteData?.title || c.entityId;
                      return (
                        <button
                          key={c.id}
                          onClick={() => {
                            setSelectedConflict(c);
                            setIsMerging(false);
                            setMergeOverrides({});
                          }}
                          className={`w-full text-left p-3 transition-colors flex flex-col gap-1 ${
                            isSelected
                              ? 'bg-indigo-50/70 dark:bg-indigo-950/40 border-l-4 border-indigo-600 dark:border-indigo-400'
                              : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                          }`}
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-semibold uppercase tracking-wider text-[10px] text-slate-500">
                              {c.entityType}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {new Date(c.detectedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className="text-xs font-medium text-slate-800 dark:text-slate-200 truncate">
                            {title}
                          </div>
                          <div className="text-[11px] text-amber-600 dark:text-amber-400 flex items-center gap-1">
                            <span>{c.reason === 'UPDATE_VS_DELETE' ? 'Update vs Delete' : 'Concurrent Edits'}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Diff Comparison & Resolution Panel */}
                <div className="lg:col-span-8 flex flex-col gap-4">
                  {selectedConflict && (
                    <>
                      {/* Conflict Summary Card */}
                      <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/20 text-xs text-slate-700 dark:text-slate-300">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-semibold text-slate-900 dark:text-slate-100">
                            {selectedConflict.localData?.title || selectedConflict.remoteData?.title || selectedConflict.entityId}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-amber-200/60 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300">
                            {selectedConflict.reason}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Local offline edits (v{selectedConflict.localVersion}) diverged from incoming remote changes (v{selectedConflict.remoteVersion}). Review differences below to select the winning record or merge fields.
                        </p>
                      </div>

                      {/* Side-by-Side Diff Table */}
                      <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden text-xs">
                        <div className="grid grid-cols-12 bg-slate-50 dark:bg-slate-900/60 p-2.5 font-semibold text-slate-700 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800">
                          <div className="col-span-3">Field</div>
                          <div className="col-span-4 flex items-center gap-1.5">
                            <Laptop className="w-3.5 h-3.5 text-indigo-500" />
                            <span>This Device (Local)</span>
                          </div>
                          <div className="col-span-5 flex items-center gap-1.5">
                            <Smartphone className="w-3.5 h-3.5 text-emerald-500" />
                            <span>Remote Device</span>
                          </div>
                        </div>

                        <div className="divide-y divide-slate-100 dark:divide-slate-800/60 max-h-56 overflow-y-auto">
                          {getRelevantFields(selectedConflict).map(({ key, localVal, remoteVal, isDifferent }) => (
                            <div
                              key={key}
                              className={`grid grid-cols-12 p-2.5 items-center ${
                                isDifferent ? 'bg-amber-50/40 dark:bg-amber-950/20 font-medium' : ''
                              }`}
                            >
                              <div className="col-span-3 text-slate-500 capitalize">{key}</div>
                              <div className="col-span-4 text-slate-800 dark:text-slate-200 break-words pr-2">
                                {isMerging ? (
                                  <input
                                    type="text"
                                    value={mergeOverrides[key] !== undefined ? mergeOverrides[key] : ''}
                                    onChange={(e) =>
                                      setMergeOverrides({ ...mergeOverrides, [key]: e.target.value })
                                    }
                                    className="w-full text-xs px-2 py-1 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b101b]"
                                  />
                                ) : (
                                  String(localVal !== undefined && localVal !== null ? localVal : '—')
                                )}
                              </div>
                              <div className="col-span-5 text-slate-800 dark:text-slate-200 break-words flex items-center justify-between">
                                <span>{String(remoteVal !== undefined && remoteVal !== null ? remoteVal : '—')}</span>
                                {isMerging && (
                                  <button
                                    type="button"
                                    onClick={() => setMergeOverrides({ ...mergeOverrides, [key]: remoteVal })}
                                    className="px-1.5 py-0.5 rounded text-[10px] bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 text-slate-700 dark:text-slate-300 ml-2 shrink-0"
                                  >
                                    Use Remote
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Resolution Actions */}
                      <div className="flex items-center justify-end gap-2.5 pt-2">
                        {isMerging ? (
                          <>
                            <button
                              type="button"
                              onClick={() => setIsMerging(false)}
                              disabled={isResolving}
                              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            >
                              Cancel Merge
                            </button>
                            <button
                              type="button"
                              onClick={() => handleSaveMerge(selectedConflict)}
                              disabled={isResolving}
                              className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors flex items-center gap-1.5"
                            >
                              <GitMerge className="w-3.5 h-3.5" />
                              Save & Synchronize Merge
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => handleStartMerge(selectedConflict)}
                              disabled={isResolving}
                              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 transition-colors flex items-center gap-1"
                            >
                              <Edit3 className="w-3.5 h-3.5" />
                              Custom Merge
                            </button>
                            <button
                              type="button"
                              onClick={() => handleKeepRemote(selectedConflict)}
                              disabled={isResolving}
                              className="px-3.5 py-1.5 text-xs font-medium rounded-lg border border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100 transition-colors"
                            >
                              Keep Remote
                            </button>
                            <button
                              type="button"
                              onClick={() => handleKeepLocal(selectedConflict)}
                              disabled={isResolving}
                              className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm transition-colors"
                            >
                              Keep Local
                            </button>
                          </>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            )
          ) : (
            /* History Tab */
            conflictHistory.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500 dark:text-slate-400">
                No past conflict resolutions recorded.
              </div>
            ) : (
              <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden divide-y divide-slate-100 dark:divide-slate-800/60 text-xs">
                {conflictHistory.map((h) => (
                  <div key={h.id} className="p-3.5 flex items-center justify-between hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                          {h.localData?.title || h.remoteData?.title || h.entityId}
                        </span>
                        <span className="uppercase text-[9px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                          {h.entityType}
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-500">
                        Resolved via <strong className="text-slate-700 dark:text-slate-300">{h.resolutionStrategy || h.status}</strong> on{' '}
                        {new Date(h.resolvedAt || h.updatedAt).toLocaleString()}
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                      {h.status}
                    </span>
                  </div>
                ))}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
