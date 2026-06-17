export interface Job {
  id: string
  url: string
  status: 'PENDING' | 'DOWNLOADING' | 'TRANSCRIBING' | 'TRANSLATING' | 'DUBBING' | 'DONE' | 'FAILED'
  error_message: string | null
  whisper_model: string
  detected_language: string | null
  transcript_length: number | null
  segment_count: number | null
  output_filename: string | null
  output_size_bytes: number | null
  created_at: string
  updated_at: string
}

export interface ApiResponse<T> {
  trace_id: string
  data: T | null
  response_status: number
  response_code: number
  response_msg: string
}

export const STAGE_ORDER = ['PENDING', 'DOWNLOADING', 'TRANSCRIBING', 'TRANSLATING', 'DUBBING', 'DONE']
export const TERMINAL_STATUSES = ['DONE', 'FAILED']

export const STAGE_LABELS: Record<string, string> = {
  PENDING: 'Queued',
  DOWNLOADING: 'Downloading video',
  TRANSCRIBING: 'Transcribing audio',
  TRANSLATING: 'Translating to Khmer',
  DUBBING: 'Synthesizing & merging',
  DONE: 'Complete',
  FAILED: 'Failed',
}

export const usePipeline = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase as string

  const _fetch = async <T>(path: string, opts?: RequestInit): Promise<ApiResponse<T>> => {
    const res = await fetch(`${base}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err?.response_msg || `HTTP ${res.status}`)
    }
    return res.json()
  }

  const submitJob = async (url: string, whisperModel = 'base'): Promise<Job> => {
    const res = await _fetch<Job>('/pipeline/jobs', {
      method: 'POST',
      body: JSON.stringify({ url, whisper_model: whisperModel }),
    })
    if (!res.data) throw new Error('No data in response')
    return res.data
  }

  const listJobs = async (): Promise<Job[]> => {
    const res = await _fetch<Job[]>('/pipeline/jobs')
    return res.data ?? []
  }

  const getJob = async (id: string): Promise<Job | null> => {
    const res = await _fetch<Job>(`/pipeline/jobs/${id}`)
    return res.data ?? null
  }

  const waitForJobUpdate = async (id: string, currentStatus: string, timeout = 25): Promise<Job | null> => {
    const params = new URLSearchParams({ current_status: currentStatus, timeout: String(timeout) })
    const res = await _fetch<Job>(`/pipeline/jobs/${id}/wait?${params}`)
    return res.data ?? null
  }

  const deleteJob = async (id: string): Promise<void> => {
    await _fetch(`/pipeline/jobs/${id}`, { method: 'DELETE' })
  }

  const getDownloadUrl = (id: string): string => `${base}/pipeline/jobs/${id}/download`

  const stageIndex = (status: string): number => STAGE_ORDER.indexOf(status)

  const isTerminal = (status: string): boolean => TERMINAL_STATUSES.includes(status)

  const formatBytes = (bytes: number | null): string => {
    if (!bytes) return '—'
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatDate = (iso: string): string => {
    return new Date(iso).toLocaleString()
  }

  const timeElapsed = (created: string, updated: string): string => {
    const ms = new Date(updated).getTime() - new Date(created).getTime()
    const s = Math.floor(ms / 1000)
    if (s < 60) return `${s}s`
    const m = Math.floor(s / 60)
    if (m < 60) return `${m}m ${s % 60}s`
    return `${Math.floor(m / 60)}h ${m % 60}m`
  }

  return {
    submitJob,
    listJobs,
    getJob,
    waitForJobUpdate,
    deleteJob,
    getDownloadUrl,
    stageIndex,
    isTerminal,
    formatBytes,
    formatDate,
    timeElapsed,
  }
}
