/**
 * Admin Panel Types
 * =================
 * 
 * Type definitions for the admin panel.
 */

// ============================================================
// Core Types
// ============================================================

export type AdminRole = 'super_admin' | 'admin' | 'support' | 'viewer'

export type AlertSeverity = 'info' | 'warning' | 'error' | 'critical'

export type AlertStatus = 'active' | 'acknowledged' | 'resolved'

export type HealthStatus = 'healthy' | 'at_risk' | 'critical'

// ============================================================
// User Types
// ============================================================

export interface FlowUsage {
  used: number
  limit: number
  packBalance: number
}

export interface AdminUserListItem {
  id: string
  email: string
  fullName?: string
  organizationId?: string
  organizationName?: string
  plan: string
  flowUsage: FlowUsage
  healthScore: number
  healthStatus: HealthStatus
  lastActive?: string
  createdAt: string
}

export interface FlowPackInfo {
  id: string
  flowsPurchased: number
  flowsRemaining: number
  purchasedAt: string
  status: string
}

export interface AdminNoteInfo {
  id: string
  content: string
  isPinned: boolean
  adminName: string
  createdAt: string
}

export interface AdminUserDetail extends AdminUserListItem {
  stripeCustomerId?: string
  subscriptionStatus?: string
  trialEndsAt?: string
  profileCompleteness: number
  totalResearches: number
  totalPreps: number
  totalFollowups: number
  errorCount30d: number
  flowPacks: FlowPackInfo[]
  adminNotes: AdminNoteInfo[]
}

export interface UserListResponse {
  users: AdminUserListItem[]
  total: number
  offset: number
  limit: number
}

export interface ActivityItem {
  id: string
  type: string
  description: string
  createdAt: string
  metadata?: Record<string, unknown>
}

export interface UserActivityResponse {
  activities: ActivityItem[]
  total: number
}

// Billing types for user detail
export interface BillingItem {
  id: string
  amountCents: number
  currency: string
  status: string
  invoiceNumber?: string
  invoicePdfUrl?: string
  paidAt?: string
  failedAt?: string
  createdAt: string
}

export interface UserBillingResponse {
  subscriptionStatus?: string
  plan: string
  currentPeriodStart?: string
  currentPeriodEnd?: string
  trialEnd?: string
  cancelAtPeriodEnd: boolean
  payments: BillingItem[]
  totalPaidCents: number
  totalPayments: number
}

// Error types for user detail
export interface ErrorItem {
  id: string
  type: string  // research, preparation, followup, knowledge_base
  title: string
  errorMessage?: string
  createdAt: string
}

export interface UserErrorsResponse {
  errors: ErrorItem[]
  total: number
  errorRate7d: number
  errorRate30d: number
}

// Health breakdown for user detail
export interface HealthBreakdown {
  activityScore: number
  errorScore: number
  usageScore: number
  profileScore: number
  paymentScore: number
  totalScore: number
  status: HealthStatus
}

// ============================================================
// Dashboard Types
// ============================================================

export interface DashboardMetrics {
  totalUsers: number
  usersGrowthWeek: number
  activeUsers7d: number
  mrrCents: number
  mrrChangePercent: number  // % change vs last month
  paidUsers: number
  activeAlerts: number
  errorRate24h: number
}

// Health Distribution (for pie chart)
export interface HealthDistribution {
  healthy: number      // 80-100 score
  atRisk: number       // 50-79 score  
  critical: number     // 0-49 score
  total: number
}

// Recent Activity (for activity feed)
export interface RecentActivityItem {
  id: string
  type: 'research' | 'preparation' | 'followup'
  userName: string
  userEmail: string
  userId: string
  title: string        // Company name or description
  status: string
  createdAt: string
}

export interface TrendDataPoint {
  date: string
  researches: number
  preps: number
  followups: number
  newUsers: number
}

export interface DashboardTrends {
  trends: TrendDataPoint[]
  periodDays: number
}

export interface AdminCheckResponse {
  isAdmin: boolean
  role: AdminRole
  adminId: string
  userId: string
}

// ============================================================
// Alert Types
// ============================================================

export interface AdminAlert {
  id: string
  alertType: string
  severity: AlertSeverity
  targetType?: string
  targetId?: string
  targetName?: string
  title: string
  description?: string
  context?: Record<string, unknown>
  status: AlertStatus
  acknowledgedBy?: string
  acknowledgedAt?: string
  resolvedBy?: string
  resolvedAt?: string
  resolutionNotes?: string
  createdAt: string
}

export interface AlertListResponse {
  alerts: AdminAlert[]
  total: number
  activeCount: number
}

// ============================================================
// Health Types
// ============================================================

export interface ServiceStatus {
  name: string
  status: 'healthy' | 'degraded' | 'down'
  responseTimeMs?: number
  lastCheck: string
  details?: string
}

export interface HealthOverview {
  overallStatus: 'healthy' | 'degraded' | 'down'
  services: ServiceStatus[]
  lastUpdated: string
}

export interface JobStats {
  name: string
  total24h: number
  completed: number
  failed: number
  successRate: number
}

export interface JobHealthResponse {
  jobs: JobStats[]
  overallSuccessRate: number
}

// ============================================================
// Billing Types
// ============================================================

export interface BillingOverview {
  mrrCents: number
  mrrFormatted: string
  arrCents: number
  arrFormatted: string
  paidUsers: number
  freeUsers: number
  trialUsers: number
  churnRate30d: number
  planDistribution: Record<string, number>
}

export interface TransactionItem {
  id: string
  organizationId: string
  organizationName?: string
  amountCents: number
  amountFormatted: string
  type: string
  status: string
  createdAt: string
}

export interface TransactionListResponse {
  transactions: TransactionItem[]
  total: number
}

export interface FailedPaymentItem {
  id: string
  customerEmail: string
  organizationName?: string
  amountCents: number
  amountFormatted: string
  attemptCount: number
  nextAttempt?: string
  createdAt: string
}

export interface FailedPaymentsResponse {
  failedPayments: FailedPaymentItem[]
  total: number
}

// ============================================================
// Audit Types
// ============================================================

export interface AuditLogEntry {
  id: string
  adminId: string
  adminEmail: string
  action: string
  targetType?: string
  targetId?: string
  targetIdentifier?: string
  details?: Record<string, unknown>
  ipAddress?: string
  userAgent?: string
  createdAt: string
}

export interface AuditLogResponse {
  entries: AuditLogEntry[]
  total: number
  hasMore: boolean
  nextCursor?: string
}

// ============================================================
// Note Types
// ============================================================

export interface NoteCreate {
  targetType: 'user' | 'organization'
  targetId: string
  content: string
  isPinned?: boolean
}

export interface NoteUpdate {
  content?: string
  isPinned?: boolean
}

export interface NoteResponse {
  id: string
  targetType: string
  targetId: string
  targetIdentifier?: string
  content: string
  isPinned: boolean
  adminId: string
  adminEmail: string
  createdAt: string
  updatedAt: string
}

export interface NoteListResponse {
  notes: NoteResponse[]
  total: number
}

// ============================================================
// Request Types
// ============================================================

export interface ResetFlowsRequest {
  reason: string
}

export interface AddFlowsRequest {
  flows: number
  reason: string
}

export interface ExtendTrialRequest {
  days: number
  reason: string
}

export interface ResolveAlertRequest {
  notes?: string
}

