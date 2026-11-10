export interface PlatformAdmin {
  id: number
  email: string
}

export interface PlatformBusiness {
  id: number
  name: string
  is_active: boolean
  onboarding_complete: boolean
  owner_id: number | null
  owner_email: string | null
  owner_is_active: boolean | null
  created_at: string | null
}

export interface PlatformBusinessPage {
  items: PlatformBusiness[]
  total: number
  offset: number
  limit: number
}

export interface PlatformInvitation {
  id: number
  email: string
  status: 'pending' | 'accepted' | 'expired' | 'revoked'
  delivery_status: 'pending' | 'sent' | 'failed'
  expires_at: string
  created_at: string
}

export interface PlatformInvitationPage {
  items: PlatformInvitation[]
  total: number
  offset: number
  limit: number
}

export interface AdminAuditEvent {
  id: number
  admin_id: number
  action: string
  entity_type: string
  entity_id: string
  outcome: string
  created_at: string
}

export interface AdminAuditPage {
  items: AdminAuditEvent[]
  total: number
  offset: number
  limit: number
}

export interface PlatformMetricCost {
  status: 'actual' | 'estimated' | 'unavailable'
  amount: string | null
  currency: string | null
  reason: string | null
  source_reference: string | null
  rate_versions: string[]
  coverage: { delivered: number; priced: number }
}

export interface PlatformMetricSummary {
  appointments: { total: number; by_status: Record<string, number> }
  customers_with_appointments: number
  messages: { total: number; by_status: Record<string, number> }
  cost: PlatformMetricCost
}

export interface PlatformMetricsResponse {
  period: { start: string; end: string; timezone: 'UTC' }
  definitions: Record<string, { source: string; formula: string }>
  global: PlatformMetricSummary
  businesses: {
    items: (PlatformMetricSummary & { business_id: number; business_name: string })[]
    total: number
    offset: number
    limit: number
  }
}
