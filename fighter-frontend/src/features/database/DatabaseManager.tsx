import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckSquare,
  Database,
  Eye,
  RefreshCw,
  RotateCcw,
  Square,
  Trash2,
  X,
} from 'lucide-react';
import type { CatalogResource } from '../../core/commands';
import { api } from '../../io/client';

interface Props {
  adminToken: string;
  onRefreshHistory: () => void;
}

export default function DatabaseManager({ adminToken, onRefreshHistory }: Props) {
  const [catalog, setCatalog] = useState<CatalogResource[]>([]);
  const [activeResourceKey, setActiveResourceKey] = useState<string>('');
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(0);
  const pageSize = 20;

  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  // Selection for bulk delete
  const [selectedIds, setSelectedIds] = useState<Set<string | number>>(new Set());

  // Confirm delete modal state
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    type: 'single' | 'batch' | 'reset-memory' | 'purge-all';
    targetId?: string | number;
    count: number;
    resourceLabel: string;
    resetTarget?: 'A' | 'B' | 'all';
  }>({ open: false, type: 'single', count: 0, resourceLabel: '' });

  // Record inspector modal state
  const [inspectItem, setInspectItem] = useState<{
    open: boolean;
    title: string;
    data: Record<string, unknown> | null;
  }>({ open: false, title: '', data: null });

  // Load catalog
  const loadCatalog = useCallback(async () => {
    if (!adminToken.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDbCatalog(adminToken.trim());
      setCatalog(res);
      if (res.length > 0 && !activeResourceKey) {
        setActiveResourceKey(res[0].key);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not fetch database catalog');
    } finally {
      setLoading(false);
    }
  }, [adminToken, activeResourceKey]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  const activeResource = catalog.find((r) => r.key === activeResourceKey);

  // Load resource items
  const loadItems = useCallback(async () => {
    if (!adminToken.trim() || !activeResourceKey) return;
    setLoading(true);
    setError(null);
    setSelectedIds(new Set());
    try {
      const res = await api.listDbResource(
        adminToken.trim(),
        activeResourceKey,
        pageSize,
        page * pageSize,
      );
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load resource items');
    } finally {
      setLoading(false);
    }
  }, [adminToken, activeResourceKey, page]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const handleSelectResource = (key: string) => {
    setActiveResourceKey(key);
    setPage(0);
    setActionNotice(null);
  };

  const toggleSelectAll = () => {
    if (!activeResource) return;
    const pk = activeResource.primaryKey;
    if (selectedIds.size === items.length) {
      setSelectedIds(new Set());
    } else {
      const all = new Set<string | number>();
      items.forEach((it) => {
        const val = it[pk];
        if (val !== undefined && val !== null) all.add(val as string | number);
      });
      setSelectedIds(all);
    }
  };

  const toggleSelectOne = (id: string | number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleInspect = async (id: string | number) => {
    if (!activeResource) return;
    try {
      const record = await api.getDbRecord(adminToken.trim(), activeResource.key, id);
      setInspectItem({
        open: true,
        title: `${activeResource.label} #${id}`,
        data: record,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to inspect record');
    }
  };

  const executeDelete = async () => {
    setError(null);
    setActionNotice(null);

    try {
      if (confirmModal.type === 'single' && confirmModal.targetId !== undefined && activeResource) {
        const res = await api.deleteDbRecord(
          adminToken.trim(),
          activeResource.key,
          confirmModal.targetId,
        );
        setActionNotice(`Successfully deleted ${res.deleted} record from ${activeResource.label}.`);
      } else if (confirmModal.type === 'batch' && activeResource) {
        const ids = Array.from(selectedIds);
        const res = await api.deleteDbBatch(adminToken.trim(), activeResource.key, ids);
        setActionNotice(`Successfully deleted ${res.deleted} records from ${activeResource.label}.`);
      } else if (confirmModal.type === 'reset-memory') {
        const target = confirmModal.resetTarget || 'all';
        const res = await api.resetMemory(adminToken.trim(), target);
        setActionNotice(
          `Memory Reset complete for ${res.target}. Cleared interval records and syntax history. Runs history was preserved.`,
        );
      } else if (confirmModal.type === 'purge-all') {
        const res = await api.purgeAllDatabase(adminToken.trim());
        setActionNotice(`Database Purge complete: ${res.message}`);
      }
      setConfirmModal({ open: false, type: 'single', count: 0, resourceLabel: '' });
      await loadCatalog();
      await loadItems();
      onRefreshHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deletion operation failed');
      setConfirmModal({ open: false, type: 'single', count: 0, resourceLabel: '' });
    }
  };

  return (
    <div className="database-manager" aria-label="Database management console">
      {/* Top Banner / Actions */}
      <div className="db-header">
        <div className="flex items-center gap-2">
          <Database size={17} />
          <div>
            <h2>Database Manager</h2>
            <p className="eyebrow">DYNAMIC CATALOG & AUDIT CONSOLE</p>
          </div>
        </div>

        <div className="db-header__actions">
          <button
            type="button"
            className="button button--reset-memory"
            onClick={() =>
              setConfirmModal({
                open: true,
                type: 'reset-memory',
                count: 0,
                resourceLabel: 'AI Notes & Libraries',
                resetTarget: 'all',
              })
            }
          >
            <RotateCcw size={13} /> Reset Memory (All)
          </button>
          <button
            type="button"
            className="button button--danger"
            onClick={() =>
              setConfirmModal({
                open: true,
                type: 'purge-all',
                count: 0,
                resourceLabel: 'Entire Database',
              })
            }
            title="Purge all tables and records from the database"
          >
            <Trash2 size={13} /> Delete All DB Data
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => {
              void loadCatalog();
              void loadItems();
            }}
            title="Refresh database catalog"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {!adminToken.trim() && (
        <div className="notice-banner">
          <AlertTriangle size={15} />
          <span>Enter the admin token in the launcher panel to enable database catalog browsing and management.</span>
        </div>
      )}

      {actionNotice && (
        <div className="success-banner" role="status">
          <span>{actionNotice}</span>
          <button type="button" onClick={() => setActionNotice(null)}>
            <X size={12} />
          </button>
        </div>
      )}

      {error && (
        <div className="error-banner" role="alert">
          <AlertCircle size={14} />
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Dynamic Catalog Navigation Tabs */}
      <div className="db-catalog-tabs" role="tablist">
        {catalog.map((res) => {
          const isActive = res.key === activeResourceKey;
          return (
            <button
              type="button"
              key={res.key}
              role="tab"
              aria-selected={isActive}
              className={`db-tab ${isActive ? 'is-active' : ''}`}
              onClick={() => handleSelectResource(res.key)}
            >
              <span>{res.label}</span>
              <span className="db-tab__count">{res.count}</span>
            </button>
          );
        })}
      </div>

      {activeResource && (
        <section className="db-content-card">
          <div className="db-content-card__head">
            <div>
              <h3>{activeResource.label}</h3>
              <p className="db-resource-desc">{activeResource.description}</p>
            </div>

            {selectedIds.size > 0 && activeResource.operations.includes('bulk_delete') && (
              <button
                type="button"
                className="button button--danger button--small"
                onClick={() =>
                  setConfirmModal({
                    open: true,
                    type: 'batch',
                    count: selectedIds.size,
                    resourceLabel: activeResource.label,
                  })
                }
              >
                <Trash2 size={13} /> Delete {selectedIds.size} selected
              </button>
            )}
          </div>

          {/* Records Table */}
          {items.length === 0 ? (
            <div className="empty-panel">
              <Database size={24} />
              <p>No records found in {activeResource.label}.</p>
            </div>
          ) : (
            <div className="db-table-wrap">
              <table className="db-table">
                <thead>
                  <tr>
                    {activeResource.operations.includes('bulk_delete') && (
                      <th style={{ width: 36 }}>
                        <button
                          type="button"
                          className="table-checkbox-btn"
                          onClick={toggleSelectAll}
                          aria-label="Select all records on page"
                        >
                          {selectedIds.size === items.length && items.length > 0 ? (
                            <CheckSquare size={14} />
                          ) : (
                            <Square size={14} />
                          )}
                        </button>
                      </th>
                    )}
                    {activeResource.fields.map((f) => (
                      <th key={f.key}>{f.label}</th>
                    ))}
                    <th style={{ width: 84, textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => {
                    const pkVal = item[activeResource.primaryKey] as string | number;
                    const isSelected = selectedIds.has(pkVal);

                    return (
                      <tr key={pkVal !== undefined ? String(pkVal) : idx} className={isSelected ? 'is-selected' : ''}>
                        {activeResource.operations.includes('bulk_delete') && (
                          <td>
                            <button
                              type="button"
                              className="table-checkbox-btn"
                              onClick={() => toggleSelectOne(pkVal)}
                              aria-label={`Select record #${pkVal}`}
                            >
                              {isSelected ? <CheckSquare size={14} /> : <Square size={14} />}
                            </button>
                          </td>
                        )}
                        {activeResource.fields.map((f) => {
                          const val = item[f.key];
                          const strVal = typeof val === 'object' && val !== null ? JSON.stringify(val) : String(val ?? '—');
                          return (
                            <td key={f.key} className={f.primary ? 'font-mono font-bold' : ''}>
                              <span className="truncate-cell" title={strVal}>
                                {strVal}
                              </span>
                            </td>
                          );
                        })}
                        <td style={{ textAlign: 'right' }}>
                          <div className="flex justify-end gap-1">
                            <button
                              type="button"
                              className="icon-button icon-button--small"
                              onClick={() => void handleInspect(pkVal)}
                              title="Inspect full JSON record"
                            >
                              <Eye size={12} />
                            </button>
                            {activeResource.operations.includes('delete') && (
                              <button
                                type="button"
                                className="icon-button icon-button--small icon-button--danger"
                                onClick={() =>
                                  setConfirmModal({
                                    open: true,
                                    type: 'single',
                                    targetId: pkVal,
                                    count: 1,
                                    resourceLabel: activeResource.label,
                                  })
                                }
                                title="Delete record"
                              >
                                <Trash2 size={12} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {total > pageSize && (
            <div className="db-pagination">
              <span>
                Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total} records
              </span>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="button button--small"
                  disabled={page === 0 || loading}
                  onClick={() => setPage(page - 1)}
                >
                  Previous
                </button>
                <button
                  type="button"
                  className="button button--small"
                  disabled={(page + 1) * pageSize >= total || loading}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Confirmation Modal */}
      {confirmModal.open && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal-dialog">
            <div className="modal-dialog__head">
              <div className="flex items-center gap-2">
                <AlertTriangle size={18} className="text-bad" />
                <h4>Confirm Destructive Action</h4>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setConfirmModal({ open: false, type: 'single', count: 0, resourceLabel: '' })}
              >
                <X size={14} />
              </button>
            </div>

            <div className="modal-dialog__body">
              {confirmModal.type === 'purge-all' ? (
                <>
                  <p>
                    Are you sure you want to <strong>PURGE ALL DATABASE DATA</strong>?
                  </p>
                  <p className="modal-note text-bad">
                    This will permanently delete ALL fight and practice run histories, replays, interval descriptions, move syntax history, AI round summaries, learned move libraries, jobs, and event streams.
                  </p>
                  <p className="modal-note font-bold text-bad mt-2">
                    THIS ACTION IS COMPLETELY IRREVERSIBLE.
                  </p>
                </>
              ) : confirmModal.type === 'reset-memory' ? (
                <>
                  <p>
                    Are you sure you want to <strong>Reset Memory</strong>?
                  </p>
                  <p className="modal-note">
                    This will delete all stored AI interval descriptions, move syntax history, and reset learned move libraries to empty.
                    <strong> Run history (saved fights and practices) will be preserved 100%.</strong>
                  </p>
                  <div className="field mt-3">
                    <span className="field__label">Target Scope</span>
                    <select
                      className="select-input"
                      value={confirmModal.resetTarget || 'all'}
                      onChange={(e) =>
                        setConfirmModal({
                          ...confirmModal,
                          resetTarget: e.target.value as 'A' | 'B' | 'all',
                        })
                      }
                    >
                      <option value="all">All Fighters (A and B)</option>
                      <option value="A">Fighter A Only</option>
                      <option value="B">Fighter B Only</option>
                    </select>
                  </div>
                </>
              ) : (
                <>
                  <p>
                    Are you sure you want to delete{' '}
                    <strong>
                      {confirmModal.count} record{confirmModal.count > 1 ? 's' : ''}
                    </strong>{' '}
                    from <strong>{confirmModal.resourceLabel}</strong>?
                  </p>
                  {confirmModal.targetId !== undefined && (
                    <p className="modal-note">Record Identifier: #{String(confirmModal.targetId)}</p>
                  )}
                  <p className="modal-note text-bad">This operation is irreversible.</p>
                </>
              )}
            </div>

            <div className="modal-dialog__foot">
              <button
                type="button"
                className="button"
                onClick={() => setConfirmModal({ open: false, type: 'single', count: 0, resourceLabel: '' })}
              >
                Cancel
              </button>
              <button type="button" className="button button--danger" onClick={() => void executeDelete()}>
                Confirm Deletion
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Record Inspector Modal */}
      {inspectItem.open && inspectItem.data && (
        <div className="modal-overlay" role="dialog" aria-modal="true">
          <div className="modal-dialog modal-dialog--wide">
            <div className="modal-dialog__head">
              <h4>{inspectItem.title}</h4>
              <button
                type="button"
                className="icon-button"
                onClick={() => setInspectItem({ open: false, title: '', data: null })}
              >
                <X size={14} />
              </button>
            </div>
            <div className="modal-dialog__body">
              <pre className="json-inspector">{JSON.stringify(inspectItem.data, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
