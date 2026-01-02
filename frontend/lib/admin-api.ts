/**
 * Admin API Client
 * ================
 * 
 * API client and React Query hooks for the admin panel.
 */

import { api } from './api'
import type {
  AdminCheckResponse,
  DashboardMetrics,
  DashboardTrends,
  HealthDistribution,
  RecentActivityItem,
  UserListResponse,
  AdminUserDetail,
  UserActivityResponse,
  UserBillingResponse,
  UserErrorsResponse,
  HealthBreakdown,
  AlertListResponse,
  AdminAlert,
  HealthOverview,
  JobHealthResponse,
  ServiceUptime,
  HealthTrendsResponse,
  IncidentsResponse,
  CostSummary,
  CostsByService,
  CostsByAction,
  CostTrend,
  CostTrendByService,
  CostsByUser,
  CostProjection,
  BillingOverview,
  TransactionListResponse,
  FailedPaymentsResponse,
  AuditLogResponse,
  NoteListResponse,
  NoteResponse,
  NoteCreate,
  NoteUpdate,
  ResetCreditsRequest,
  AddCreditsRequest,
  ExtendTrialRequest,
  ChangePlanRequest,
  SuspendUserRequest,
  UnsuspendUserRequest,
  DeleteUserRequest,
  ResolveAlertRequest,
  AvailablePlan,
} from '@/types/admin'

const BASE = '/api/v1/admin'

// ============================================================
// Dashboard API
// ============================================================

export const adminApi = {
  // Check admin access
  checkAccess: async (): Promise<AdminCheckResponse> => {
    const response = await api.get<AdminCheckResponse>(`${BASE}/dashboard/check`)
    return response.data as AdminCheckResponse
  },

  // Get dashboard metrics
  getMetrics: async (): Promise<DashboardMetrics> => {
    const response = await api.get<DashboardMetrics>(`${BASE}/dashboard/metrics`)
    return response.data as DashboardMetrics
  },

  // Get usage trends
  getTrends: async (days = 7): Promise<DashboardTrends> => {
    const response = await api.get<DashboardTrends>(`${BASE}/dashboard/trends?days=${days}`)
    return response.data as DashboardTrends
  },

  // Get health distribution (for pie chart)
  getHealthDistribution: async (): Promise<HealthDistribution> => {
    const response = await api.get<HealthDistribution>(`${BASE}/dashboard/health-distribution`)
    return response.data as HealthDistribution
  },

  // Get recent activity feed
  getRecentActivity: async (limit = 10): Promise<{ activities: RecentActivityItem[] }> => {
    const response = await api.get<{ activities: RecentActivityItem[] }>(`${BASE}/dashboard/recent-activity?limit=${limit}`)
    return response.data as { activities: RecentActivityItem[] }
  },

  // ============================================================
  // Users API
  // ============================================================

  // List users
  listUsers: async (params: {
    search?: string
    plan?: string
    healthStatus?: string
    sortBy?: string
    sortOrder?: string
    offset?: number
    limit?: number
  }): Promise<UserListResponse> => {
    const query = new URLSearchParams()
    if (params.search) query.set('search', params.search)
    if (params.plan) query.set('plan', params.plan)
    if (params.healthStatus) query.set('health_status', params.healthStatus)
    if (params.sortBy) query.set('sort_by', params.sortBy)
    if (params.sortOrder) query.set('sort_order', params.sortOrder)
    if (params.offset) query.set('offset', params.offset.toString())
    if (params.limit) query.set('limit', params.limit.toString())
    
    const response = await api.get<UserListResponse>(`${BASE}/users?${query.toString()}`)
    return response.data as UserListResponse
  },

  // Get user detail
  getUser: async (userId: string): Promise<AdminUserDetail> => {
    const response = await api.get<AdminUserDetail>(`${BASE}/users/${userId}`)
    return response.data as AdminUserDetail
  },

  // Get user activity
  getUserActivity: async (userId: string, limit = 50): Promise<UserActivityResponse> => {
    const response = await api.get<UserActivityResponse>(`${BASE}/users/${userId}/activity?limit=${limit}`)
    return response.data as UserActivityResponse
  },

  // Reset user's monthly credits
  resetCredits: async (userId: string, data: ResetCreditsRequest): Promise<{ success: boolean; message: string }> => {
    const response = await api.post<{ success: boolean; message: string }>(`${BASE}/users/${userId}/reset-credits`, data)
    return response.data as { success: boolean; message: string }
  },

  // Add bonus credits
  addCredits: async (userId: string, data: AddCreditsRequest): Promise<{ success: boolean; message: string }> => {
    const response = await api.post<{ success: boolean; message: string }>(`${BASE}/users/${userId}/add-credits`, {
      credits: data.credits,
      reason: data.reason,
    })
    return response.data as { success: boolean; message: string }
  },

  // Extend trial
  extendTrial: async (userId: string, data: ExtendTrialRequest): Promise<{ success: boolean; message: string; newEnd: string }> => {
    const response = await api.post<{ success: boolean; message: string; newEnd: string }>(`${BASE}/users/${userId}/extend-trial`, data)
    return response.data as { success: boolean; message: string; newEnd: string }
  },

  // Get available plans
  getAvailablePlans: async (): Promise<{ plans: AvailablePlan[] }> => {
    const response = await api.get<{ plans: AvailablePlan[] }>(`${BASE}/users/plans/available`)
    return response.data as { plans: AvailablePlan[] }
  },

  // Change user plan
  changePlan: async (userId: string, data: ChangePlanRequest): Promise<{ success: boolean; message: string; oldPlan: string; newPlan: string }> => {
    const response = await api.patch<{ success: boolean; message: string; oldPlan: string; newPlan: string }>(
      `${BASE}/users/${userId}/plan`,
      {
        plan_id: data.planId,
        reason: data.reason,
      }
    )
    return response.data as { success: boolean; message: string; oldPlan: string; newPlan: string }
  },

  // Suspend user
  suspendUser: async (userId: string, data: SuspendUserRequest): Promise<{ success: boolean; message: string }> => {
    const response = await api.post<{ success: boolean; message: string }>(`${BASE}/users/${userId}/suspend`, data)
    return response.data as { success: boolean; message: string }
  },

  // Unsuspend user
  unsuspendUser: async (userId: string, data: UnsuspendUserRequest): Promise<{ success: boolean; message: string }> => {
    const response = await api.post<{ success: boolean; message: string }>(`${BASE}/users/${userId}/unsuspend`, data)
    return response.data as { success: boolean; message: string }
  },

  // Delete user (super admin only)
  deleteUser: async (userId: string, data: DeleteUserRequest): Promise<{ success: boolean; message: string; deletedUserId: string; deletedOrganizationId?: string }> => {
    // Use POST with _method override since axios delete doesn't support body well
    const response = await api.post<{ success: boolean; message: string; deletedUserId: string; deletedOrganizationId?: string }>(
      `${BASE}/users/${userId}/delete`,
      data
    )
    return response.data as { success: boolean; message: string; deletedUserId: string; deletedOrganizationId?: string }
  },

  // Export user data
  exportUser: async (userId: string): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(`${BASE}/users/${userId}/export`)
    return response.data as Record<string, unknown>
  },

  // Get user billing history
  getUserBilling: async (userId: string): Promise<UserBillingResponse> => {
    const response = await api.get<UserBillingResponse>(`${BASE}/users/${userId}/billing`)
    return response.data as UserBillingResponse
  },

  // Get user errors
  getUserErrors: async (userId: string, limit = 50): Promise<UserErrorsResponse> => {
    const response = await api.get<UserErrorsResponse>(`${BASE}/users/${userId}/errors?limit=${limit}`)
    return response.data as UserErrorsResponse
  },

  // Get user health breakdown
  getUserHealthBreakdown: async (userId: string): Promise<HealthBreakdown> => {
    const response = await api.get<HealthBreakdown>(`${BASE}/users/${userId}/health-breakdown`)
    return response.data as HealthBreakdown
  },

  // ============================================================
  // Notes API
  // ============================================================

  // List notes
  listNotes: async (params: {
    targetType?: string
    targetId?: string
  }): Promise<NoteListResponse> => {
    const query = new URLSearchParams()
    if (params.targetType) query.set('target_type', params.targetType)
    if (params.targetId) query.set('target_id', params.targetId)
    
    const response = await api.get<NoteListResponse>(`${BASE}/notes?${query.toString()}`)
    return response.data as NoteListResponse
  },

  // Create note
  createNote: async (data: NoteCreate): Promise<NoteResponse> => {
    const response = await api.post<NoteResponse>(`${BASE}/notes`, {
      target_type: data.targetType,
      target_id: data.targetId,
      content: data.content,
      is_pinned: data.isPinned ?? false,
    })
    return response.data as NoteResponse
  },

  // Update note
  updateNote: async (noteId: string, data: NoteUpdate): Promise<NoteResponse> => {
    const response = await api.patch<NoteResponse>(`${BASE}/notes/${noteId}`, {
      content: data.content,
      is_pinned: data.isPinned,
    })
    return response.data as NoteResponse
  },

  // Delete note
  deleteNote: async (noteId: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(`${BASE}/notes/${noteId}`)
    return response.data as { success: boolean }
  },

  // ============================================================
  // Alerts API
  // ============================================================

  // List alerts
  listAlerts: async (params: {
    status?: string
    severity?: string
    alertType?: string
    limit?: number
    offset?: number
  }): Promise<AlertListResponse> => {
    const query = new URLSearchParams()
    if (params.status) query.set('status', params.status)
    if (params.severity) query.set('severity', params.severity)
    if (params.alertType) query.set('alert_type', params.alertType)
    if (params.limit) query.set('limit', params.limit.toString())
    if (params.offset) query.set('offset', params.offset.toString())
    
    const response = await api.get<AlertListResponse>(`${BASE}/alerts?${query.toString()}`)
    return response.data as AlertListResponse
  },

  // Get single alert
  getAlert: async (alertId: string): Promise<AdminAlert> => {
    const response = await api.get<AdminAlert>(`${BASE}/alerts/${alertId}`)
    return response.data as AdminAlert
  },

  // Acknowledge alert
  acknowledgeAlert: async (alertId: string): Promise<{ success: boolean }> => {
    const response = await api.post<{ success: boolean }>(`${BASE}/alerts/${alertId}/acknowledge`)
    return response.data as { success: boolean }
  },

  // Resolve alert
  resolveAlert: async (alertId: string, data: ResolveAlertRequest): Promise<{ success: boolean }> => {
    const response = await api.post<{ success: boolean }>(`${BASE}/alerts/${alertId}/resolve`, data)
    return response.data as { success: boolean }
  },

  // Bulk acknowledge
  bulkAcknowledgeAlerts: async (alertIds: string[]): Promise<{ success: boolean; acknowledgedCount: number }> => {
    const response = await api.post<{ success: boolean; acknowledgedCount: number }>(`${BASE}/alerts/bulk-acknowledge`, alertIds)
    return response.data as { success: boolean; acknowledgedCount: number }
  },

  // ============================================================
  // Health API
  // ============================================================

  // Get health overview
  getHealthOverview: async (): Promise<HealthOverview> => {
    const response = await api.get<HealthOverview>(`${BASE}/health/overview`)
    return response.data as HealthOverview
  },

  // Get job health
  getJobHealth: async (): Promise<JobHealthResponse> => {
    const response = await api.get<JobHealthResponse>(`${BASE}/health/jobs`)
    return response.data as JobHealthResponse
  },

  // Get service uptime
  getServiceUptime: async (): Promise<ServiceUptime[]> => {
    const response = await api.get<ServiceUptime[]>(`${BASE}/health/uptime`)
    return response.data as ServiceUptime[]
  },

  // Get health trends
  getHealthTrends: async (days: number = 30): Promise<HealthTrendsResponse> => {
    const response = await api.get<HealthTrendsResponse>(`${BASE}/health/trends?days=${days}`)
    return response.data as HealthTrendsResponse
  },

  // Get recent incidents
  getRecentIncidents: async (limit: number = 50, service?: string): Promise<IncidentsResponse> => {
    const query = new URLSearchParams({ limit: limit.toString() })
    if (service) query.set('service', service)
    const response = await api.get<IncidentsResponse>(`${BASE}/health/incidents?${query.toString()}`)
    return response.data as IncidentsResponse
  },

  // ============================================================
  // Cost API
  // ============================================================

  // Get cost summary
  getCostSummary: async (days: number = 30): Promise<CostSummary> => {
    const response = await api.get<CostSummary>(`${BASE}/costs/summary?days=${days}`)
    return response.data as CostSummary
  },

  // Get costs by service
  getCostsByService: async (days: number = 30): Promise<CostsByService> => {
    const response = await api.get<CostsByService>(`${BASE}/costs/by-service?days=${days}`)
    return response.data as CostsByService
  },

  // Get costs by action
  getCostsByAction: async (days: number = 30): Promise<CostsByAction> => {
    const response = await api.get<CostsByAction>(`${BASE}/costs/by-action?days=${days}`)
    return response.data as CostsByAction
  },

  // Get cost trend
  getCostTrend: async (days: number = 30): Promise<CostTrend> => {
    const response = await api.get<CostTrend>(`${BASE}/costs/trend?days=${days}`)
    return response.data as CostTrend
  },

  // Get cost trend by service
  getCostTrendByService: async (days: number = 30): Promise<CostTrendByService> => {
    const response = await api.get<CostTrendByService>(`${BASE}/costs/trend-by-service?days=${days}`)
    return response.data as CostTrendByService
  },

  // Get top users by cost
  getTopUsersByCost: async (days: number = 30, limit: number = 20): Promise<CostsByUser> => {
    const response = await api.get<CostsByUser>(`${BASE}/costs/top-users?days=${days}&limit=${limit}`)
    return response.data as CostsByUser
  },

  // Get cost projection
  getCostProjection: async (): Promise<CostProjection> => {
    const response = await api.get<CostProjection>(`${BASE}/costs/projection`)
    return response.data as CostProjection
  },

  // ============================================================
  // Billing API
  // ============================================================

  // Get billing overview
  getBillingOverview: async (): Promise<BillingOverview> => {
    const response = await api.get<BillingOverview>(`${BASE}/billing/overview`)
    return response.data as BillingOverview
  },

  // Get transactions
  getTransactions: async (params: {
    type?: string
    limit?: number
    offset?: number
  }): Promise<TransactionListResponse> => {
    const query = new URLSearchParams()
    if (params.type) query.set('type', params.type)
    if (params.limit) query.set('limit', params.limit.toString())
    if (params.offset) query.set('offset', params.offset.toString())
    
    const response = await api.get<TransactionListResponse>(`${BASE}/billing/transactions?${query.toString()}`)
    return response.data as TransactionListResponse
  },

  // Get failed payments
  getFailedPayments: async (): Promise<FailedPaymentsResponse> => {
    const response = await api.get<FailedPaymentsResponse>(`${BASE}/billing/failed-payments`)
    return response.data as FailedPaymentsResponse
  },

  // ============================================================
  // Audit API
  // ============================================================

  // Get audit log
  getAuditLog: async (params: {
    action?: string
    targetType?: string
    adminId?: string
    dateFrom?: string
    dateTo?: string
    search?: string
    limit?: number
    cursor?: string
  }): Promise<AuditLogResponse> => {
    const query = new URLSearchParams()
    if (params.action) query.set('action', params.action)
    if (params.targetType) query.set('target_type', params.targetType)
    if (params.adminId) query.set('admin_id', params.adminId)
    if (params.dateFrom) query.set('date_from', params.dateFrom)
    if (params.dateTo) query.set('date_to', params.dateTo)
    if (params.search) query.set('search', params.search)
    if (params.limit) query.set('limit', params.limit.toString())
    if (params.cursor) query.set('cursor', params.cursor)
    
    const response = await api.get<AuditLogResponse>(`${BASE}/audit?${query.toString()}`)
    return response.data as AuditLogResponse
  },

  // Get action types
  getActionTypes: async (): Promise<{ actions: string[] }> => {
    const response = await api.get<{ actions: string[] }>(`${BASE}/audit/actions`)
    return response.data as { actions: string[] }
  },

  // Export audit log
  exportAuditLog: async (params: {
    action?: string
    targetType?: string
    dateFrom?: string
    dateTo?: string
    limit?: number
  }): Promise<Blob> => {
    const query = new URLSearchParams()
    if (params.action) query.set('action', params.action)
    if (params.targetType) query.set('target_type', params.targetType)
    if (params.dateFrom) query.set('date_from', params.dateFrom)
    if (params.dateTo) query.set('date_to', params.dateTo)
    if (params.limit) query.set('limit', params.limit.toString())
    
    const response = await api.get<Blob>(`${BASE}/audit/export?${query.toString()}`)
    return response.data as Blob
  },

  // ============================================================
  // Affiliate API
  // ============================================================

  // List affiliates
  listAffiliates: async (params: {
    page?: number
    pageSize?: number
    status?: string
    search?: string
  }): Promise<AffiliateListResponse> => {
    const query = new URLSearchParams()
    if (params.page) query.set('page', params.page.toString())
    if (params.pageSize) query.set('page_size', params.pageSize.toString())
    if (params.status) query.set('status', params.status)
    if (params.search) query.set('search', params.search)
    
    const response = await api.get<AffiliateListResponse>(`${BASE}/affiliates?${query.toString()}`)
    return response.data as AffiliateListResponse
  },

  // Get affiliate stats
  getAffiliateStats: async (): Promise<AffiliateProgramStats> => {
    const response = await api.get<AffiliateProgramStats>(`${BASE}/affiliates/stats`)
    return response.data as AffiliateProgramStats
  },

  // Get affiliate detail
  getAffiliateDetail: async (affiliateId: string): Promise<AffiliateDetail> => {
    const response = await api.get<AffiliateDetail>(`${BASE}/affiliates/${affiliateId}`)
    return response.data as AffiliateDetail
  },

  // Update affiliate status
  updateAffiliateStatus: async (affiliateId: string, status: string, reason?: string): Promise<{ success: boolean }> => {
    const response = await api.patch<{ success: boolean }>(`${BASE}/affiliates/${affiliateId}/status`, {
      status,
      reason,
    })
    return response.data as { success: boolean }
  },

  // Update affiliate commission rates
  updateAffiliateRates: async (affiliateId: string, rates: {
    commission_rate_subscription?: number
    commission_rate_credits?: number
  }): Promise<{ success: boolean; updated: Record<string, number> }> => {
    const response = await api.patch<{ success: boolean; updated: Record<string, number> }>(
      `${BASE}/affiliates/${affiliateId}/commission-rates`,
      rates
    )
    return response.data as { success: boolean; updated: Record<string, number> }
  },

  // Trigger manual payout
  triggerAffiliatePayout: async (affiliateId: string): Promise<{ success: boolean; payout?: any }> => {
    const response = await api.post<{ success: boolean; payout?: any }>(
      `${BASE}/affiliates/${affiliateId}/trigger-payout`
    )
    return response.data as { success: boolean; payout?: any }
  },

  // Sync Connect status
  syncAffiliateConnect: async (affiliateId: string): Promise<{ success: boolean }> => {
    const response = await api.post<{ success: boolean }>(
      `${BASE}/affiliates/${affiliateId}/sync-connect`
    )
    return response.data as { success: boolean }
  },
}

// ============================================================
// Affiliate Types
// ============================================================

export interface AffiliateListItem {
  id: string
  user_id: string
  organization_id: string
  affiliate_code: string
  status: string
  stripe_connect_status: string
  stripe_payouts_enabled: boolean
  total_clicks: number
  total_signups: number
  total_conversions: number
  total_earned_cents: number
  total_paid_cents: number
  current_balance_cents: number
  created_at: string
  activated_at: string | null
  user_email: string | null
  user_name: string | null
}

export interface AffiliateListResponse {
  affiliates: AffiliateListItem[]
  total: number
  page: number
  page_size: number
}

export interface AffiliateProgramStats {
  total_affiliates: number
  active_affiliates: number
  pending_affiliates: number
  total_referrals: number
  total_conversions: number
  total_revenue_cents: number
  total_commissions_cents: number
  total_paid_cents: number
  pending_payouts_cents: number
}

export interface AffiliateDetail {
  affiliate: any
  user: any
  organization: any
  recent_referrals: any[]
  recent_commissions: any[]
  recent_payouts: any[]
  stats: any
}
