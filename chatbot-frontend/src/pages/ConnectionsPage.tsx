import { useState } from 'react'
import {
  useConnections,
  useCreateConnection,
  useDeleteConnection,
  useTestConnection,
  useIntrospect,
  useTables,
  useAvailableTables,
  useUpdateConnection,
} from '@/hooks/useConnections'
import type { Connection, ConnectionCreate, TableSummary, AvailableTable } from '@/types/api'
import { cn } from '@/lib/utils'
import {
  Plus, Trash2, PlugZap, RefreshCw, Table2, ChevronRight, ChevronLeft,
  AlertCircle, CheckCircle2, XCircle, Loader2,
} from 'lucide-react'

// ── Helpers ────────────────────────────────────────────────────────────────────
function tableKey(schema: string, table: string) {
  return `${schema}.${table}`
}

// ── Simple notification store ──────────────────────────────────────────────────
interface Toast {
  id: string
  title: string
  message: string
  type: 'success' | 'error'
}

let toastId = 0
const listeners: Array<(toasts: Toast[]) => void> = []
let toasts: Toast[] = []

function notify(toast: Omit<Toast, 'id'>) {
  const id = String(++toastId)
  toasts = [...toasts, { ...toast, id }]
  listeners.forEach((l) => l(toasts))
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id)
    listeners.forEach((l) => l(toasts))
  }, 4000)
}

function useToasts() {
  const [list, setList] = useState<Toast[]>(toasts)
  useState(() => {
    const cb = (t: Toast[]) => setList([...t])
    listeners.push(cb)
    return () => {
      const idx = listeners.indexOf(cb)
      if (idx !== -1) listeners.splice(idx, 1)
    }
  })
  return list
}

function ToastContainer() {
  const toastList = useToasts()
  if (toastList.length === 0) return null
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toastList.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-start gap-2 px-4 py-3 rounded-xl border shadow-lg text-sm',
            t.type === 'success'
              ? 'bg-green-50 border-green-200 text-green-800 dark:bg-green-950/50 dark:border-green-800 dark:text-green-300'
              : 'bg-red-50 border-red-200 text-red-800 dark:bg-red-950/50 dark:border-red-800 dark:text-red-300',
          )}
        >
          {t.type === 'success'
            ? <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0" />
            : <XCircle className="h-4 w-4 mt-0.5 shrink-0" />}
          <div>
            <p className="font-semibold leading-tight">{t.title}</p>
            <p className="text-xs opacity-80 mt-0.5">{t.message}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Input component ────────────────────────────────────────────────────────────
function Input({
  label,
  error,
  required,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label?: string; error?: string; required?: boolean }) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="text-xs font-medium text-foreground">
          {label}
          {required && <span className="text-destructive ml-0.5">*</span>}
        </label>
      )}
      <input
        className={cn(
          'w-full px-3 py-2 text-sm rounded-lg border bg-background text-foreground',
          'placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring',
          error ? 'border-destructive' : 'border-input',
        )}
        {...props}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

function Textarea({
  label,
  error,
  required,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: string; error?: string; required?: boolean }) {
  return (
    <div className="space-y-1">
      {label && (
        <label className="text-xs font-medium text-foreground">
          {label}
          {required && <span className="text-destructive ml-0.5">*</span>}
        </label>
      )}
      <textarea
        className={cn(
          'w-full px-3 py-2 text-sm rounded-lg border bg-background text-foreground font-mono',
          'placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none',
          error ? 'border-destructive' : 'border-input',
        )}
        rows={4}
        {...props}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

function Select({
  label,
  options,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string
  options: { value: string; label: string }[]
}) {
  return (
    <div className="space-y-1">
      {label && <label className="text-xs font-medium text-foreground">{label}</label>}
      <select
        className="w-full px-3 py-2 text-sm rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        {...props}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}

function NumberInput({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label?: string }) {
  return (
    <div className="space-y-1">
      {label && <label className="text-xs font-medium text-foreground">{label}</label>}
      <input
        type="number"
        className="w-full px-3 py-2 text-sm rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        {...props}
      />
    </div>
  )
}

// ── Modal ──────────────────────────────────────────────────────────────────────
function Modal({
  open,
  onClose,
  title,
  children,
  size = 'md',
}: {
  open: boolean
  onClose: () => void
  title: React.ReactNode
  children: React.ReactNode
  size?: 'md' | 'lg' | 'xl'
}) {
  if (!open) return null
  const widths = { md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className={cn('relative w-full bg-card rounded-2xl shadow-2xl border border-border overflow-hidden', widths[size])}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="text-sm font-semibold text-foreground">{title}</div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-accent transition-colors">
            <XCircle className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>
        <div className="p-5 overflow-y-auto max-h-[80vh] custom-scrollbar">{children}</div>
      </div>
    </div>
  )
}

// ── Schema Explorer ────────────────────────────────────────────────────────────
function SchemaExplorer({ connectionId }: { connectionId: string }) {
  const { data: tables, isLoading } = useTables(connectionId)
  const [expanded, setExpanded] = useState<string | null>(null)

  if (isLoading)
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Loading tables...
      </div>
    )
  if (!tables || tables.length === 0)
    return <p className="text-sm text-muted-foreground mt-2">No tables. Run introspection first.</p>

  return (
    <div className="mt-3 space-y-1">
      {tables.map((t: TableSummary) => (
        <div key={t.id} className="border border-border rounded-lg overflow-hidden">
          <button
            className="w-full flex items-center justify-between px-3 py-2 text-sm hover:bg-muted transition-colors"
            onClick={() => setExpanded(expanded === t.id ? null : t.id)}
          >
            <span className="font-mono text-xs font-medium">
              {t.schema_name}.{t.table_name}
            </span>
            <div className="flex items-center gap-1.5">
              <span className="px-1.5 py-0.5 text-[10px] bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 rounded">
                {t.column_count} cols
              </span>
              {t.row_count_estimate != null && (
                <span className="px-1.5 py-0.5 text-[10px] bg-muted text-muted-foreground rounded">
                  ~{t.row_count_estimate.toLocaleString()} rows
                </span>
              )}
            </div>
          </button>
          {expanded === t.id && t.comment && (
            <div className="px-3 py-2 bg-muted/30 border-t border-border text-xs text-muted-foreground">
              {t.comment}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Table Manager Modal ────────────────────────────────────────────────────────
function TableManagerModal({
  connection,
  open,
  onClose,
}: {
  connection: Connection
  open: boolean
  onClose: () => void
}) {
  const updateMutation = useUpdateConnection(connection.id)
  const { data: availableTables, isLoading, isError } = useAvailableTables(connection.id, open)
  const [whitelist, setWhitelist] = useState<string[]>(connection.allowed_table_names ?? [])
  const [availableSearch, setAvailableSearch] = useState('')
  const [whitelistSearch, setWhitelistSearch] = useState('')

  const whitelistSet = new Set(whitelist.map((n) => n.toLowerCase()))
  const candidates: AvailableTable[] = (availableTables ?? []).filter(
    (t) => !whitelistSet.has(tableKey(t.schema_name, t.table_name).toLowerCase()),
  )
  const filteredCandidates = candidates.filter((t) =>
    t.table_name.toLowerCase().includes(availableSearch.toLowerCase()),
  )
  const filteredWhitelist = whitelist.filter((n) =>
    n.toLowerCase().includes(whitelistSearch.toLowerCase()),
  )

  const addTable = (t: AvailableTable) => {
    const key = tableKey(t.schema_name, t.table_name)
    setWhitelist((prev) => [...prev, key].sort())
  }
  const removeTable = (key: string) => setWhitelist((prev) => prev.filter((k) => k !== key))
  const addAll = () => {
    const keys = filteredCandidates.map((t) => tableKey(t.schema_name, t.table_name))
    setWhitelist((prev) => [...new Set([...prev, ...keys])].sort())
  }
  const removeAll = () => {
    const toRemove = new Set(filteredWhitelist.map((k) => k.toLowerCase()))
    setWhitelist((prev) => prev.filter((k) => !toRemove.has(k.toLowerCase())))
  }

  const handleSave = () => {
    updateMutation.mutate(
      { allowed_table_names: whitelist.length > 0 ? whitelist : [] },
      {
        onSuccess: () => {
          notify({
            type: 'success',
            title: 'Whitelist saved',
            message: whitelist.length > 0
              ? `${whitelist.length} tables whitelisted`
              : 'Whitelist cleared — all dbo tables included',
          })
          onClose()
        },
        onError: () => notify({ type: 'error', title: 'Save failed', message: 'Could not update table whitelist.' }),
      },
    )
  }

  return (
    <Modal open={open} onClose={onClose} title={`Manage Tables — ${connection.name}`} size="xl">
      <div className="space-y-4">
        <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-xs text-blue-700 dark:text-blue-300">
          <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>Only <strong>dbo</strong> tables shown. Save then re-run introspection to apply.</span>
        </div>

        {isError && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            Failed to load available tables. Check the connection is active.
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          {/* Available */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">
                Available ({filteredCandidates.length})
              </span>
              <button
                className="text-xs text-blue-600 hover:underline disabled:opacity-40"
                disabled={filteredCandidates.length === 0}
                onClick={addAll}
              >
                Add all
              </button>
            </div>
            <input
              placeholder="Search tables..."
              value={availableSearch}
              onChange={(e) => setAvailableSearch(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <div className="h-80 overflow-y-auto border border-border rounded-lg custom-scrollbar">
              {isLoading ? (
                <div className="h-full flex items-center justify-center">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : filteredCandidates.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                  {candidates.length === 0 ? 'All whitelisted' : 'No matches'}
                </div>
              ) : (
                <div className="p-1 space-y-0.5">
                  {filteredCandidates.map((t) => {
                    const key = tableKey(t.schema_name, t.table_name)
                    return (
                      <div key={key} className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted group">
                        <span className="text-xs font-mono truncate">{key}</span>
                        <button
                          onClick={() => addTable(t)}
                          className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-blue-100 dark:hover:bg-blue-900/40 text-blue-600 transition-all"
                        >
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Whitelisted */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground">
                Whitelisted ({filteredWhitelist.length}{whitelistSearch ? ` of ${whitelist.length}` : ''})
              </span>
              <button
                className="text-xs text-destructive hover:underline disabled:opacity-40"
                disabled={filteredWhitelist.length === 0}
                onClick={removeAll}
              >
                Remove all
              </button>
            </div>
            <input
              placeholder="Search whitelist..."
              value={whitelistSearch}
              onChange={(e) => setWhitelistSearch(e.target.value)}
              className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-input bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            />
            <div className="h-80 overflow-y-auto border border-border rounded-lg custom-scrollbar">
              {whitelist.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center gap-1 text-xs text-muted-foreground">
                  <span>No tables whitelisted</span>
                  <span>All dbo tables will be included</span>
                </div>
              ) : filteredWhitelist.length === 0 ? (
                <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
                  No matches
                </div>
              ) : (
                <div className="p-1 space-y-0.5">
                  {filteredWhitelist.map((key) => (
                    <div key={key} className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-muted group">
                      <button
                        onClick={() => removeTable(key)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/40 text-destructive transition-all"
                      >
                        <ChevronLeft className="h-3.5 w-3.5" />
                      </button>
                      <span className="text-xs font-mono truncate flex-1 ml-1">{key}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-border">
          <span className="text-xs text-muted-foreground">
            {whitelist.length === 0
              ? 'No whitelist — all dbo tables included on introspection'
              : `${whitelist.length} table${whitelist.length !== 1 ? 's' : ''} whitelisted`}
          </span>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-border hover:bg-accent transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {updateMutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </Modal>
  )
}

// ── Add Connection Modal ───────────────────────────────────────────────────────
interface FormValues {
  name: string
  connector_type: string
  connection_string: string
  bq_project_id: string
  bq_credentials_json: string
  db_server_hostname: string
  db_http_path: string
  db_access_token: string
  db_catalog: string
  default_schema: string
  max_query_timeout_seconds: string
  max_rows: string
}

const defaultForm: FormValues = {
  name: '',
  connector_type: 'postgresql',
  connection_string: '',
  bq_project_id: '',
  bq_credentials_json: '',
  db_server_hostname: '',
  db_http_path: '',
  db_access_token: '',
  db_catalog: 'main',
  default_schema: 'public',
  max_query_timeout_seconds: '30',
  max_rows: '1000',
}

function AddConnectionModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createMutation = useCreateConnection()
  const [form, setForm] = useState<FormValues>(defaultForm)
  const [errors, setErrors] = useState<Partial<Record<keyof FormValues, string>>>({})

  const set = (k: keyof FormValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [k]: e.target.value }))

  const isBigQuery = form.connector_type === 'bigquery'
  const isDatabricks = form.connector_type === 'databricks'
  const isSqlServer = form.connector_type === 'sqlserver'

  const validate = (): boolean => {
    const errs: Partial<Record<keyof FormValues, string>> = {}
    if (!form.name.trim()) errs.name = 'Name is required'
    if (['postgresql', 'sqlserver'].includes(form.connector_type) && !form.connection_string.trim())
      errs.connection_string = 'Connection string is required'
    if (isBigQuery) {
      if (!form.bq_project_id.trim()) errs.bq_project_id = 'Project ID is required'
      if (!form.bq_credentials_json.trim()) {
        errs.bq_credentials_json = 'Service account JSON is required'
      } else {
        try { JSON.parse(form.bq_credentials_json) } catch { errs.bq_credentials_json = 'Invalid JSON' }
      }
    }
    if (isDatabricks) {
      if (!form.db_server_hostname.trim()) errs.db_server_hostname = 'Server hostname is required'
      if (!form.db_http_path.trim()) errs.db_http_path = 'HTTP path is required'
      if (!form.db_access_token.trim()) errs.db_access_token = 'Access token is required'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!validate()) return

    let connectionString = form.connection_string
    let defaultSchema = form.default_schema

    if (isBigQuery) {
      connectionString = JSON.stringify({
        project_id: form.bq_project_id,
        credentials_json: JSON.parse(form.bq_credentials_json),
      })
      if (!defaultSchema || defaultSchema === 'public') defaultSchema = ''
    } else if (isDatabricks) {
      connectionString = JSON.stringify({
        server_hostname: form.db_server_hostname,
        http_path: form.db_http_path,
        access_token: form.db_access_token,
        catalog: form.db_catalog || 'main',
      })
      if (!defaultSchema || defaultSchema === 'public') defaultSchema = 'default'
    } else if (isSqlServer) {
      if (!defaultSchema || defaultSchema === 'public') defaultSchema = 'dbo'
    }

    const payload: ConnectionCreate = {
      name: form.name,
      connector_type: form.connector_type,
      connection_string: connectionString,
      default_schema: defaultSchema,
      max_query_timeout_seconds: parseInt(form.max_query_timeout_seconds) || 30,
      max_rows: parseInt(form.max_rows) || 1000,
    }

    createMutation.mutate(payload, {
      onSuccess: () => {
        notify({ type: 'success', title: 'Connection created', message: `"${form.name}" added successfully` })
        setForm(defaultForm)
        setErrors({})
        onClose()
      },
      onError: (err: unknown) =>
        notify({
          type: 'error',
          title: 'Error',
          message: err instanceof Error ? err.message : 'Failed to create connection',
        }),
    })
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Database Connection" size="lg">
      <form onSubmit={handleSubmit} className="space-y-3">
        <Input label="Name" required placeholder="My Production DB" value={form.name} onChange={set('name')} error={errors.name} />
        <Select
          label="Connector type"
          value={form.connector_type}
          onChange={set('connector_type')}
          options={[
            { value: 'postgresql', label: 'PostgreSQL' },
            { value: 'sqlserver', label: 'SQL Server' },
            { value: 'bigquery', label: 'BigQuery' },
            { value: 'databricks', label: 'Databricks' },
          ]}
        />

        {isBigQuery ? (
          <>
            <Input label="Project ID" required placeholder="my-gcp-project" value={form.bq_project_id} onChange={set('bq_project_id')} error={errors.bq_project_id} />
            <Textarea label="Service account JSON" required placeholder="Paste service account key JSON" value={form.bq_credentials_json} onChange={set('bq_credentials_json')} error={errors.bq_credentials_json} />
          </>
        ) : isDatabricks ? (
          <>
            <Input label="Server hostname" required placeholder="dbc-xxx.cloud.databricks.com" value={form.db_server_hostname} onChange={set('db_server_hostname')} error={errors.db_server_hostname} />
            <Input label="HTTP path" required placeholder="/sql/1.0/warehouses/..." value={form.db_http_path} onChange={set('db_http_path')} error={errors.db_http_path} />
            <Input label="Access token" required type="password" placeholder="dapi..." value={form.db_access_token} onChange={set('db_access_token')} error={errors.db_access_token} />
            <Input label="Catalog" placeholder="main" value={form.db_catalog} onChange={set('db_catalog')} />
          </>
        ) : (
          <Input
            label="Connection string"
            required
            placeholder={
              isSqlServer
                ? 'SERVER=localhost,1433;DATABASE=master;UID=sa;PWD=...;'
                : 'postgresql://user:pass@host:5432/dbname'
            }
            value={form.connection_string}
            onChange={set('connection_string')}
            error={errors.connection_string}
          />
        )}

        <Input
          label={isBigQuery ? 'Dataset' : 'Default schema'}
          placeholder={isBigQuery ? 'my_dataset' : isDatabricks || isSqlServer ? 'dbo' : 'public'}
          value={form.default_schema}
          onChange={set('default_schema')}
        />

        <div className="grid grid-cols-2 gap-3">
          <NumberInput label="Query timeout (s)" min={1} max={300} value={form.max_query_timeout_seconds} onChange={set('max_query_timeout_seconds')} />
          <NumberInput label="Max rows" min={1} max={100000} value={form.max_rows} onChange={set('max_rows')} />
        </div>

        {isSqlServer && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-xs text-blue-700 dark:text-blue-300">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>Only <strong>dbo</strong> schema tables will be introspected. Use <strong>Manage Tables</strong> after creation to set a whitelist.</span>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-accent transition-colors">
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {createMutation.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ── Badge ──────────────────────────────────────────────────────────────────────
function Badge({ label, color = 'gray' }: { label: string; color?: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
    gray: 'bg-muted text-muted-foreground',
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    violet: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  }
  return (
    <span className={cn('px-2 py-0.5 text-[10px] font-medium rounded-full', colors[color] ?? colors.gray)}>
      {label}
    </span>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────
export function ConnectionsPage() {
  const [addOpen, setAddOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tableManagerConn, setTableManagerConn] = useState<Connection | null>(null)

  const { data: connections, isLoading } = useConnections()
  const deleteMutation = useDeleteConnection()
  const testMutation = useTestConnection()
  const introspectMutation = useIntrospect()

  const handleTest = (id: string) => {
    testMutation.mutate(id, {
      onSuccess: (res) =>
        notify({
          type: res.success ? 'success' : 'error',
          title: res.success ? 'Connected' : 'Failed',
          message: res.success ? 'Connection successful' : res.message || 'Connection failed',
        }),
    })
  }

  const handleIntrospect = (id: string) => {
    introspectMutation.mutate(id, {
      onSuccess: (res) =>
        notify({
          type: 'success',
          title: 'Introspection complete',
          message: `Found ${res.tables_found} tables, ${res.columns_found} columns`,
        }),
    })
  }

  const handleDelete = (id: string) => {
    if (!confirm('Delete this connection?')) return
    deleteMutation.mutate(id)
  }

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-foreground">Database Connections</h1>
          <button
            onClick={() => setAddOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add Connection
          </button>
        </div>

        {isLoading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {!isLoading && (!connections || connections.length === 0) && (
          <div className="text-center py-12 border border-dashed border-border rounded-2xl">
            <Database className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">No connections yet. Add one to get started.</p>
          </div>
        )}

        {connections?.map((conn: Connection) => (
          <div key={conn.id} className="bg-card border border-border rounded-2xl p-4 space-y-3">
            {/* Top row */}
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center flex-wrap gap-1.5">
                <span className="font-semibold text-sm text-foreground">{conn.name}</span>
                <Badge label={conn.connector_type} color="blue" />
                <Badge label={conn.is_active ? 'active' : 'inactive'} color={conn.is_active ? 'green' : 'gray'} />
                {conn.connector_type === 'sqlserver' && (
                  <Badge
                    label={conn.allowed_table_names?.length ? `${conn.allowed_table_names.length} tables` : 'dbo only'}
                    color="violet"
                  />
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => handleTest(conn.id)}
                  disabled={testMutation.isPending && testMutation.variables === conn.id}
                  className="p-1.5 rounded-lg hover:bg-accent text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                  title="Test connection"
                >
                  {testMutation.isPending && testMutation.variables === conn.id
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <PlugZap className="h-4 w-4" />}
                </button>
                <button
                  onClick={() => handleIntrospect(conn.id)}
                  disabled={introspectMutation.isPending && introspectMutation.variables === conn.id}
                  className="p-1.5 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/40 text-blue-600 transition-colors disabled:opacity-50"
                  title="Introspect schema"
                >
                  {introspectMutation.isPending && introspectMutation.variables === conn.id
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <RefreshCw className="h-4 w-4" />}
                </button>
                {conn.connector_type === 'sqlserver' && (
                  <button
                    onClick={() => setTableManagerConn(conn)}
                    className="p-1.5 rounded-lg hover:bg-violet-100 dark:hover:bg-violet-900/40 text-violet-600 transition-colors"
                    title="Manage table whitelist"
                  >
                    <Table2 className="h-4 w-4" />
                  </button>
                )}
                <button
                  onClick={() => handleDelete(conn.id)}
                  className="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 text-destructive transition-colors"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Meta */}
            <p className="text-xs text-muted-foreground">
              Schema: <span className="font-mono">{conn.default_schema}</span>
              {' · '}Timeout: {conn.max_query_timeout_seconds}s
              {' · '}Max rows: {conn.max_rows.toLocaleString()}
            </p>
            {conn.last_introspected_at && (
              <p className="text-[10px] text-muted-foreground">
                Last introspected: {new Date(conn.last_introspected_at).toLocaleString()}
              </p>
            )}

            {/* Tables toggle */}
            <button
              className="text-xs text-blue-600 hover:underline"
              onClick={() => setSelectedId(selectedId === conn.id ? null : conn.id)}
            >
              {selectedId === conn.id ? 'Hide tables' : 'Show tables'}
            </button>
            {selectedId === conn.id && <SchemaExplorer connectionId={conn.id} />}
          </div>
        ))}
      </div>

      <AddConnectionModal open={addOpen} onClose={() => setAddOpen(false)} />
      {tableManagerConn && (
        <TableManagerModal
          connection={tableManagerConn}
          open={!!tableManagerConn}
          onClose={() => setTableManagerConn(null)}
        />
      )}
      <ToastContainer />
    </div>
  )
}

// Missing import fix
function Database(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <ellipse cx="12" cy="5" rx="9" ry="3" />
      <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
    </svg>
  )
}
